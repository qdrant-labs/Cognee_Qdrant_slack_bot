"""Compile the decision graph into an agentic SKILL.

Retrieval only helps an agent that thinks to ask. Most of the time it doesn't — it
just writes the code, and reintroduces the choice the team rejected in March.

So we go the other way: walk the graph for decisions that are still live plus the
constraints that outlived them, and emit a Claude Code skill. The next agent that
touches the vector store loads the team's decision history as a precondition instead
of having to query for it.

    python compile_skill.py --out ../.claude/skills
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

import bootstrap  # noqa: F401  (loads .env, registers the Qdrant adapter)

from ledger import Ledger, load_ledger  # noqa: E402

SKILL_SLUG = "team-decision-history"

FRONTMATTER = """---
name: {slug}
description: >-
  The team's live architectural decisions and the constraints they must respect,
  compiled from Slack history. Load before choosing or changing a vector store,
  embedding store, or database, before reopening a settled infrastructure choice,
  or whenever asked why a component was picked. Contains decisions that were already
  rejected — check here before proposing one of them again.
---
"""


def render(led: Ledger) -> str:
    dead = led.superseded_ids()
    live = [d for did, d in led.decisions.items() if did not in dead]
    superseded = [d for did, d in led.decisions.items() if did in dead]
    newer_of = {older: newer for newer, older in led.supersedes}

    lines = [FRONTMATTER.format(slug=SKILL_SLUG)]
    lines.append(f"# Team decision history\n")
    lines.append(
        f"Compiled from the Slack workspace graph on {date.today().isoformat()} by "
        f"`compile_skill.py`. Do not hand-edit — rerun the compiler.\n"
    )

    lines.append("## Decisions currently in force\n")
    if live:
        for decision in live:
            lines.append(f"- **{decision.name}**")
            if decision.decided_on or decision.decided_by:
                who = decision.decided_by or "unknown"
                when = decision.decided_on or "unknown date"
                lines.append(f"  - decided {when} by {who}")
            if decision.description:
                lines.append(f"  - {decision.description}")
    else:
        lines.append("- (none extracted)")
    lines.append("")

    lines.append("## Already rejected — do not propose these again\n")
    if superseded:
        for decision in superseded:
            replacement = led.decisions.get(newer_of.get(decision.id, ""))
            lines.append(f"- **{decision.name}** — superseded")
            if replacement:
                when = f" on {replacement.decided_on}" if replacement.decided_on else ""
                lines.append(f"  - replaced{when} by: {replacement.name}")
                if replacement.description:
                    lines.append(f"  - reason: {replacement.description}")
    else:
        lines.append("- (none extracted)")
    lines.append("")

    lines.append("## Constraints that outlive individual decisions\n")
    if led.constraints:
        for constraint in led.constraints.values():
            lines.append(f"- **{constraint.name}**")
            if constraint.description:
                lines.append(f"  - {constraint.description}")
    else:
        lines.append("- (none extracted)")
    lines.append("")

    lines.append("## How to use this\n")
    lines.append(
        "Before implementing anything that touches these areas, check the rejected list. "
        "If the task asks for something on it, say so and cite the decision that replaced "
        "it rather than silently complying. Every constraint above applies to new work "
        "unless the user explicitly lifts it.\n"
    )
    lines.append(
        "For anything not covered here, query the live graph:\n\n"
        "```bash\npython demo.py -q \"your question\"\n```\n"
    )
    return "\n".join(lines)


async def main_async(out_dir: Path) -> None:
    led = await load_ledger()
    skill_dir = out_dir / SKILL_SLUG
    skill_dir.mkdir(parents=True, exist_ok=True)
    target = skill_dir / "SKILL.md"
    target.write_text(render(led))

    dead = led.superseded_ids()
    print(f"Wrote {target}")
    print(
        f"  {len(led.decisions) - len(dead)} live decision(s), "
        f"{len(dead)} superseded, {len(led.constraints)} constraint(s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / ".claude" / "skills",
        help="Skills directory to write into (default: ./.claude/skills)",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.out))


if __name__ == "__main__":
    main()
