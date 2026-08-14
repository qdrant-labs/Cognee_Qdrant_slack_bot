"""The two-minute demo: one question, answered by plain vector search and by the
decision ledger, side by side.

    python demo.py                      # default question, as the backend lead
    python demo.py --as contractor      # same question, narrower clearance
    python demo.py -q "why did we ..."  # anything else
"""

from __future__ import annotations

import argparse
import asyncio

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from retrieve import ledger_view, naive, persona_name

console = Console(width=140)

DEFAULT_QUESTION = "Why aren't we using Postgres for the vector store, and what are we using now?"
DEFAULT_KEYWORDS = ["pgvector", "postgres", "qdrant", "vector", "embedding", "quantization"]


def naive_panel(answer: str) -> Panel:
    return Panel(
        Text(answer, style="white"),
        title="[bold red]1. NAIVE VECTOR SEARCH[/]  (Qdrant top-k → LLM)",
        subtitle="[red]no structure, no clearance[/]",
        border_style="red",
        padding=(1, 2),
    )


def ledger_panel(view: dict, persona: str) -> Panel:
    body = Text()
    body.append(view["answer"] + "\n", style="white")

    if view["lineage"]:
        body.append("\nDecision lineage (walked on the graph, not guessed)\n", style="bold cyan")
        for line in view["lineage"]:
            style = "bold green" if "LIVE" in line else "dim strike"
            body.append(line + "\n", style=style)

    if view["constraints"]:
        body.append("\nConstraints still in force\n", style="bold cyan")
        for constraint in view["constraints"][:6]:
            body.append(f"   • {constraint}\n", style="yellow")

    body.append("\nClearance\n", style="bold cyan")
    body.append(f"   {persona_name(persona)}\n", style="white")
    body.append(f"   channels: {', '.join(view['channels'])}\n", style="dim")
    if view["withheld"]:
        body.append(
            f"   ⚠ {view['withheld']} source(s) matched but withheld (not cleared)\n",
            style="bold magenta",
        )
    else:
        body.append("   nothing withheld at this clearance level\n", style="dim")

    return Panel(
        body,
        title="[bold green]2. DECISION LEDGER[/]  (cognee typed graph → Qdrant)",
        subtitle="[green]lineage + clearance[/]",
        border_style="green",
        padding=(1, 2),
    )


async def run(question: str, persona: str, keywords: list[str]) -> None:
    console.rule(f"[bold]{question}")
    console.print()

    with console.status("[dim]querying both retrieval paths...", spinner="dots"):
        naive_answer, view = await asyncio.gather(
            naive(question), ledger_view(question, persona, keywords)
        )

    console.print(
        Columns(
            [naive_panel(naive_answer), ledger_panel(view, persona)],
            equal=True,
            expand=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-q", "--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--as",
        dest="persona",
        default="eng-lead",
        help="Which persona is asking: eng-lead, contractor, finance",
    )
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS)
    args = parser.parse_args()

    asyncio.run(run(args.question, args.persona, args.keywords))


if __name__ == "__main__":
    main()
