"""Slack Block Kit templates for CVlizer."""

from typing import Any, Dict, List
from cvlizer.matcher import CandidateMatch, MatchResult


def create_help_block() -> List[Dict[str, Any]]:
    """Generates the startup / help Block Kit card."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🤖 CVlizer — AI Talent Matcher",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How to use CVlizer:*\n"
                    "Mention `@CVlizer` anywhere with a Job Description or role requirements, e.g.:\n\n"
                    "> `@CVlizer We need a Staff Backend Engineer with Python, FastAPI, Kafka and distributed systems experience to lead our payments team.`\n\n"
                    "CVlizer will index the job into Cognee, search the candidate knowledge graph in Qdrant, and deliver the top 3 best fits with measured vector similarity, LLM fit score, and CV quotes!"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 *Powered by Cognee Knowledge Graphs, Qdrant Vector DB & Groq LLMs*",
                }
            ],
        },
    ]


def create_loading_block(job_snippet: str) -> List[Dict[str, Any]]:
    """Initial immediate acknowledgment card posted in thread."""
    preview = job_snippet[:150] + ("..." if len(job_snippet) > 150 else "")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔎 *Analyzing Job & Indexing into Cognee...*\n> _{preview}_",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "⏳ Searching Qdrant vector space & traversing candidate knowledge graph...",
                }
            ],
        },
    ]


def create_match_results_block(result: MatchResult) -> List[Dict[str, Any]]:
    """Builds the rich Block Kit presentation for Top 3 candidates."""
    blocks: List[Dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🎯 Top Candidate Matches",
                "emoji": True,
            },
        }
    ]

    if not result.candidates:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "⚠️ *No matching candidates found in the talent database.* Try broadening your job description requirements.",
                },
            }
        )
        return blocks

    rank_emojis = ["🥇", "🥈", "🥉"]

    for idx, candidate in enumerate(result.candidates[:3]):
        emoji = rank_emojis[idx] if idx < len(rank_emojis) else "👤"
        rank_num = idx + 1

        # Candidate Header
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{emoji} #{rank_num}: {candidate.name}*\n"
                        f"📊 *Measured Vector Match:* `{candidate.cosine_score}%`  |  🧠 *Fit Score:* `{candidate.fit_score}/100`"
                    ),
                },
            }
        )

        # Reasoning Section
        if candidate.reason:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"💡 *Why Hire:*\n{candidate.reason}",
                    },
                }
            )

        # Quotes Section
        if candidate.quotes:
            quote_text = "\n".join([f"> • \"_{q}_\"" for q in candidate.quotes])
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📄 *Key Evidence from CV:*\n{quote_text}",
                    },
                }
            )

        blocks.append({"type": "divider"})

    # Footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "✨ *Ranked deterministically via Qdrant cosine similarity + Cognee graph reasoning.*",
                }
            ],
        }
    )

    return blocks
