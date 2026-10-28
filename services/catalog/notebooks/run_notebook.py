"""Execute the exploration notebook in place and strip the noise a run leaves behind.

    uv run --group notebooks python services/catalog/notebooks/run_notebook.py
    uv run --group notebooks python services/catalog/notebooks/run_notebook.py --embedder bge-m3 \
        --output /tmp/semantic_matching.bge-m3.ipynb

The committed notebook is the output of the default run (hash embedder, all items). This script
does what ``jupyter nbconvert --to notebook --execute --inplace`` does, minus the parts that make
every refresh a noisy diff: per-cell timing metadata and the Python version in ``language_info``.
It needs the ``notebooks`` dependency group (``uv sync --group notebooks``).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK = Path(__file__).resolve().parent / "semantic_matching.ipynb"


def execute(path: Path, output: Path, *, embedder: str, sample: int, timeout: int = 1800) -> None:
    os.environ["SMARTCART_NB_EMBEDDER"] = embedder  # the kernel inherits the environment
    os.environ["SMARTCART_NB_SAMPLE"] = str(sample)
    nb = nbformat.read(path, as_version=4)
    NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        record_timing=False,
        resources={"metadata": {"path": str(path.parent)}},
    ).execute()
    nb.metadata["language_info"] = {"name": "python"}
    nbformat.write(nb, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--notebook", type=Path, default=NOTEBOOK)
    parser.add_argument("--output", type=Path, help="write here instead of in place")
    parser.add_argument("--embedder", default="hash", help="hash (default), bge-m3 or e5")
    parser.add_argument("--sample", type=int, default=0, help="N items of each kind; 0 means all")
    args = parser.parse_args()
    output = args.output or args.notebook
    execute(args.notebook, output, embedder=args.embedder, sample=args.sample)
    print(f"executed {args.notebook} -> {output}")


if __name__ == "__main__":
    main()
