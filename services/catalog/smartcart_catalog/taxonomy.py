"""Product taxonomy v1 (issue #10): load and validate ``data/taxonomy.yaml``, query it.

The file lists nodes with a stable dotted id (``dairy.milk.fresh``). The parent is the id without
its last segment and the level is the number of segments, so the structure cannot drift from the
ids. Validation checks what the database cannot: every parent exists, ids are well formed, levels
are 1 to 4, and there are exactly 19 departments. ``seed.py`` writes the nodes to Postgres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import yaml

DEPARTMENT_COUNT = 19
MAX_LEVEL = 4
_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")


def default_data_dir() -> Path:
    """``<repo>/data``: services/catalog/smartcart_catalog/taxonomy.py -> parents[3]."""
    return Path(__file__).resolve().parents[3] / "data"


class TaxonomyError(ValueError):
    """The taxonomy file is inconsistent. The message lists every problem found."""


@dataclass(frozen=True)
class TaxonomyNode:
    id: str
    name_he: str
    name_en: str | None
    sort: int

    @property
    def level(self) -> int:
        return self.id.count(".") + 1

    @property
    def parent_id(self) -> str | None:
        return self.id.rsplit(".", 1)[0] if "." in self.id else None


@dataclass(frozen=True)
class Taxonomy:
    nodes: tuple[TaxonomyNode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {n.id: n for n in self.nodes})

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._by_id  # type: ignore[attr-defined]

    def __len__(self) -> int:
        return len(self.nodes)

    def get(self, node_id: str) -> TaxonomyNode:
        return self._by_id[node_id]  # type: ignore[attr-defined]

    def departments(self) -> list[TaxonomyNode]:
        return [n for n in self.nodes if n.level == 1]

    def children(self, node_id: str) -> list[TaxonomyNode]:
        return [n for n in self.nodes if n.parent_id == node_id]

    def path(self, node_id: str) -> list[TaxonomyNode]:
        """Root-to-node chain, e.g. dairy > dairy.milk > dairy.milk.fresh."""
        parts = node_id.split(".")
        return [self.get(".".join(parts[: i + 1])) for i in range(len(parts))]

    def path_he(self, node_id: str) -> str:
        """Hebrew breadcrumb, used as ``category_path`` context in extraction prompts."""
        return " > ".join(n.name_he for n in self.path(node_id))

    def leaves(self) -> list[TaxonomyNode]:
        parents = {n.parent_id for n in self.nodes}
        return [n for n in self.nodes if n.id not in parents]


def parse_taxonomy(doc: dict[str, Any]) -> Taxonomy:
    """Build and validate a taxonomy from the parsed YAML document."""
    raw = doc.get("nodes") if isinstance(doc, dict) else None
    if not isinstance(raw, list):
        raise TaxonomyError("taxonomy file must have a 'nodes' list")
    problems: list[str] = []
    nodes: list[TaxonomyNode] = []
    seen: set[str] = set()
    for sort, entry in enumerate(raw):
        if not isinstance(entry, dict):
            problems.append(f"entry {sort}: not a mapping")
            continue
        node_id = str(entry.get("id", ""))
        name_he = str(entry.get("name_he") or "").strip()
        unknown = set(entry) - {"id", "name_he", "name_en"}
        if unknown:
            problems.append(f"{node_id}: unknown fields {sorted(unknown)}")
        if not node_id or not all(_SEGMENT.match(s) for s in node_id.split(".")):
            problems.append(f"entry {sort}: bad id {node_id!r} (lowercase dotted slug)")
            continue
        if node_id in seen:
            problems.append(f"{node_id}: duplicate id")
        seen.add(node_id)
        if not name_he:
            problems.append(f"{node_id}: missing name_he")
        node = TaxonomyNode(node_id, name_he, entry.get("name_en"), sort)
        if node.level > MAX_LEVEL:
            problems.append(f"{node_id}: level {node.level} deeper than {MAX_LEVEL}")
        nodes.append(node)
    for node in nodes:
        if node.parent_id is not None and node.parent_id not in seen:
            problems.append(f"{node.id}: parent {node.parent_id} does not exist")
    departments = [n for n in nodes if n.level == 1]
    if len(departments) != DEPARTMENT_COUNT:
        problems.append(f"expected {DEPARTMENT_COUNT} departments, found {len(departments)}")
    if problems:
        raise TaxonomyError("invalid taxonomy:\n  " + "\n  ".join(problems))
    return Taxonomy(tuple(nodes))


def load_taxonomy(path: Path | None = None) -> Taxonomy:
    path = path or default_data_dir() / "taxonomy.yaml"
    return parse_taxonomy(yaml.safe_load(path.read_text(encoding="utf-8")))


# --- queries ------------------------------------------------------------------------------------


def canonicals_under(conn: psycopg.Connection, node_id: str) -> list[tuple[int, str]]:
    """``(id, slug)`` of every canonical product at ``node_id`` or below it, by rank."""
    rows = conn.execute(
        "SELECT id, slug FROM canonical_products"
        " WHERE taxonomy_id = %(n)s OR taxonomy_id LIKE %(prefix)s"
        " ORDER BY rank NULLS LAST, slug",
        {"n": node_id, "prefix": node_id.replace("_", r"\_") + ".%"},
    ).fetchall()
    return [(r[0], r[1]) for r in rows]
