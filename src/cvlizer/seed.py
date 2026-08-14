"""CV Seeder: Ingests candidate CVs into Cognee and Qdrant."""

import asyncio
import os
import re
import sys
from pathlib import Path
import cognee
import cvlizer.config  # ensures Qdrant adapter registration and env loading

DEFAULT_CVS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cvs"


def slugify(text: str) -> str:
    """Generate a clean slug identifier from a name or filename."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text)


async def load_and_seed_cvs(cvs_dir: Path = DEFAULT_CVS_DIR, prune_first: bool = True):
    """
    Ingests all markdown CVs in cvs_dir into Cognee with dataset='cvs'
    and node_set=['cv', 'candidate:<slug>'].
    """
    if not cvs_dir.exists():
        print(f"Directory {cvs_dir} not found.")
        sys.exit(1)

    cv_files = sorted(list(cvs_dir.glob("*.md")))
    if not cv_files:
        print(f"No markdown CV files found in {cvs_dir}.")
        sys.exit(1)

    if prune_first:
        print("🧹 Cleaning up previous Cognee data...")
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(graph=True, vector=True, metadata=True, cache=True)
        print("Database pruned.")

    print(f"\n📂 Ingesting {len(cv_files)} candidate CVs into dataset 'cvs'...")

    for file_path in cv_files:
        slug = slugify(file_path.stem)
        candidate_tag = f"candidate:{slug}"
        content = file_path.read_text(encoding="utf-8")
        
        first_line = content.strip().split("\n")[0]
        name = first_line.replace("#", "").strip() if first_line.startswith("#") else file_path.stem

        print(f"  + Ingesting: {name} (tag: {candidate_tag})")
        await cognee.add(
            content,
            dataset_name="cvs",
            node_set=["cv", candidate_tag],
        )

    print("\n🧠 Running cognee.cognify(datasets=['cvs'], data_per_batch=2)...")
    await cognee.cognify(datasets=["cvs"], data_per_batch=2)
    print("\n✨ All candidate CVs are indexed into Qdrant & Knowledge Graph!")


if __name__ == "__main__":
    prune = "--no-prune" not in sys.argv
    asyncio.run(load_and_seed_cvs(prune_first=prune))
