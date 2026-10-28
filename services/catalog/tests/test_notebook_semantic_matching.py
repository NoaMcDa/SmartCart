"""Smoke test of the semantic-matching exploration notebook (``services/catalog/notebooks``).

The notebook is executed end to end with nbclient, offline, under the hash embedder and a small
sample (``SMARTCART_NB_SAMPLE=300``), so it stays a few seconds. It needs the optional ``notebooks``
dependency group (``uv sync --group notebooks``); without it the executing tests are skipped with
that reason. The checks on the committed file read plain JSON and always run.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "semantic_matching.ipynb"
SKIP_REASON = "notebook dependencies are not installed: uv sync --group notebooks"
SAMPLE = 300


def _results(nb) -> dict:
    """The ``RESULTS {...}`` line the last cell prints."""
    for cell in reversed(nb["cells"]):
        for out in cell.get("outputs", []):
            text = out.get("text", "")
            text = "".join(text) if isinstance(text, list) else text
            match = re.search(r"^RESULTS (\{.*\})$", text, re.MULTILINE)
            if match:
                return json.loads(match.group(1))
    raise AssertionError("no RESULTS line in the notebook outputs")


def _execute(monkeypatch, tmp_path, embedder: str):
    nbformat = pytest.importorskip("nbformat", reason=SKIP_REASON)
    nbclient = pytest.importorskip("nbclient", reason=SKIP_REASON)
    for module in ("ipykernel", "sklearn", "matplotlib", "numpy"):
        pytest.importorskip(module, reason=SKIP_REASON)
    from jupyter_client.kernelspec import NoSuchKernel

    monkeypatch.setenv("SMARTCART_NB_EMBEDDER", embedder)
    monkeypatch.setenv("SMARTCART_NB_SAMPLE", str(SAMPLE))
    monkeypatch.delenv("SMARTCART_NB_THRESHOLD", raising=False)
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = nbclient.NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
        record_timing=False,
        resources={"metadata": {"path": str(tmp_path)}},
    )
    try:
        client.execute()
    except NoSuchKernel:
        pytest.skip("no 'python3' Jupyter kernel is installed (ipykernel)")
    return nb


def test_notebook_runs_offline_with_hash_embedder_on_a_sample(monkeypatch, tmp_path):
    nb = _execute(monkeypatch, tmp_path, "hash")
    results = _results(nb)
    assert results["embedder"] == "hash"
    assert results["model"] == "hash-ngram-2-3-4-v1"
    assert 0 < results["real_items"] <= SAMPLE
    assert 0 < results["gold_items"] <= SAMPLE
    assert results["barcode_positives"] > 0
    for key in ("barcode_recall", "gold_any_brand_precision", "gold_any_brand_recall"):
        assert 0.0 <= results[key] <= 1.0, key
    # the judge's veto only removes pairs: it can never add a critical error
    assert results["gold_critical_wrong_pairs_hard_rules"] <= results["gold_critical_wrong_pairs"]
    assert (
        results["gold_critical_wrong_pairs_hard_rules_pct"]
        <= (results["gold_critical_wrong_pairs_hard_rules"])
    )
    assert results["barcode_recall_hard_rules"] <= results["barcode_recall"] + 1e-9
    assert results["runtime_seconds"] < 120


@pytest.mark.skipif(
    importlib.util.find_spec("sentence_transformers") is not None,
    reason="sentence-transformers is installed, so a bge-m3 request would try to download the model",
)
def test_unavailable_model_is_skipped_cleanly_and_the_notebook_goes_on(monkeypatch, tmp_path):
    nb = _execute(monkeypatch, tmp_path, "bge-m3")
    results = _results(nb)
    assert results["embedder"] == "hash"
    assert results["status"].startswith("fallback")
    streams = "".join(
        out.get("text", "")
        for cell in nb["cells"]
        for out in cell.get("outputs", [])
        if out.get("output_type") == "stream"
    )
    assert "SKIPPED embedder 'bge-m3'" in streams


def test_committed_notebook_has_outputs_and_no_local_paths():
    raw = NOTEBOOK.read_text(encoding="utf-8")
    nb = json.loads(raw)
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert code, "the notebook has no code cells"
    assert all(c["execution_count"] is not None for c in code), "a code cell was never executed"
    assert not any(o.get("output_type") == "error" for c in code for o in c["outputs"])
    assert not re.search(r"/home/|/tmp/|/root/|worktree", raw), "a local path leaked into the file"
    assert all("execution" not in c["metadata"] for c in nb["cells"]), "timing metadata left in"
    results = _results(nb)
    assert results["embedder"] == "hash"
    assert results["real_items"] > 1000, "commit the default run (all items), not a sample"
    assert results["gold_items"] > 800
