"""Record a real run of the demo as an SVG, for submission proof.

Runs the same question at two clearance levels in one capture, so the difference
the ACL layer makes is visible in a single image. Nothing is staged: this drives
demo.run() exactly as `make demo` does and records what comes back.

    python capture_demo.py            # -> proof/demo-run.svg + proof/demo-run.txt
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

import demo

OUT_DIR = Path(__file__).parent / "proof"


async def main() -> None:
    console = Console(width=140, record=True)
    demo.console = console  # demo.run() writes through the module-level console

    for persona in ("eng-lead", "contractor"):
        console.print()
        console.rule(f"[bold yellow]asking as: {persona}")
        await demo.run(demo.DEFAULT_QUESTION, persona, demo.DEFAULT_KEYWORDS)

    OUT_DIR.mkdir(exist_ok=True)
    svg = OUT_DIR / "demo-run.svg"
    txt = OUT_DIR / "demo-run.txt"
    # Both exporters drain the record buffer by default, so the first one must not.
    txt.write_text(console.export_text(clear=False))
    console.save_svg(str(svg), title="make demo — Decision Ledger")
    print(f"\nWrote {svg}\nWrote {txt}")


if __name__ == "__main__":
    asyncio.run(main())
