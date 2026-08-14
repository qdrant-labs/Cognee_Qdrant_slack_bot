"""Unit tests for CVlizer matcher, Block Kit rendering, and text processing without LLM calls."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from cvlizer.matcher import (
    CandidateMatch,
    MatchResult,
    extract_json_block,
    match_job,
)
from cvlizer.blocks import (
    create_help_block,
    create_loading_block,
    create_match_results_block,
)
from cvlizer.slack_app import clean_mention_text


def test_extract_json_block():
    # Markdown code fence JSON
    text_with_fences = """Here is the evaluation:
```json
[
  {
    "name": "Alice Chen",
    "fit_score": 95,
    "quotes": ["FastAPI expert"],
    "reason": "Strong background"
  }
]
```
Let me know if you need more info."""
    extracted = extract_json_block(text_with_fences)
    assert extracted is not None
    assert len(extracted) == 1
    assert extracted[0]["name"] == "Alice Chen"
    assert extracted[0]["fit_score"] == 95

    # Direct raw JSON
    raw_json = '{"candidates": [{"name": "Bob", "fit_score": 80}]}'
    extracted_raw = extract_json_block(raw_json)
    assert extracted_raw is not None
    assert "candidates" in extracted_raw


def test_clean_mention_text():
    text = "<@U12345678> We need a Senior Frontend Engineer with React."
    assert clean_mention_text(text) == "We need a Senior Frontend Engineer with React."
    assert clean_mention_text("<@W98765432>") == ""


def test_block_kit_generation():
    help_blocks = create_help_block()
    assert len(help_blocks) >= 3

    loading_blocks = create_loading_block("Looking for SRE with Kubernetes")
    assert len(loading_blocks) == 2

    # Match Result blocks
    dummy_result = MatchResult(
        job_description="Staff Backend Engineer",
        candidates=[
            CandidateMatch(
                name="Alice Chen",
                slug="alice_chen",
                cosine_score=92.5,
                fit_score=95,
                quotes=["Architected high-throughput payment ingestion pipeline handling 65,000 req/sec."],
                reason="Direct experience with high-load distributed systems.",
            )
        ],
    )
    result_blocks = create_match_results_block(dummy_result)
    assert len(result_blocks) >= 4
    # Check that candidate name and scores appear
    block_texts = str(result_blocks)
    assert "Alice Chen" in block_texts
    assert "92.5%" in block_texts
    assert "95/100" in block_texts


@pytest.mark.asyncio
async def test_match_job_mocked():
    # Mock vector engine chunks
    mock_chunk_1 = MagicMock()
    mock_chunk_1.score = 0.94
    mock_chunk_1.payload = {
        "belongs_to_set": ["cv", "candidate:alice_chen"],
        "text": "# Alice Chen\nSenior Backend Engineer",
    }

    mock_chunk_2 = MagicMock()
    mock_chunk_2.score = 0.88
    mock_chunk_2.payload = {
        "belongs_to_set": ["cv", "candidate:devon_adams"],
        "text": "# Devon Adams\nStaff SRE",
    }

    mock_engine = AsyncMock()
    mock_engine.search.return_value = [mock_chunk_1, mock_chunk_2]

    graph_response = [
        """```json
[
  {
    "name": "Alice Chen",
    "fit_score": 96,
    "quotes": ["Expert in FastAPI and Kafka"],
    "reason": "Exceptional match for backend systems"
  }
]
```"""
    ]

    with patch("cvlizer.matcher.get_vector_engine_async", return_value=mock_engine), \
         patch("cognee.search", new_callable=AsyncMock) as mock_search, \
         patch("cognee.add", new_callable=AsyncMock), \
         patch("cognee.cognify", new_callable=AsyncMock):

        mock_search.return_value = graph_response

        res = await match_job("Senior Backend Engineer with Python and Kafka", index_job=True)

        assert len(res.candidates) == 2
        top = res.candidates[0]
        assert top.name == "Alice Chen"
        assert top.cosine_score == 94.0
        assert top.fit_score == 96
        assert len(top.quotes) == 1
        assert "Exceptional match" in top.reason
