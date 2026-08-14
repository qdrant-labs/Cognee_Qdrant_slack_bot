"""Transport-agnostic job matcher leveraging Cognee and Qdrant."""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

import cognee
from cognee.infrastructure.databases.vector import get_vector_engine_async
import cvlizer.config  # ensures adapter registration and env loading


class CandidateMatch(BaseModel):
    name: str
    slug: str
    cosine_score: float = Field(default=0.0, description="Measured Qdrant vector similarity (0-100%)")
    fit_score: int = Field(default=0, description="LLM reasoned fit score (0-100)")
    quotes: List[str] = Field(default_factory=list, description="Direct quotes from candidate's CV")
    reason: str = Field(default="", description="Reasoning for match/hiring")
    raw_snippet: Optional[str] = None


class MatchResult(BaseModel):
    job_description: str
    candidates: List[CandidateMatch]
    raw_graph_response: Optional[str] = None


def extract_json_block(text: str) -> Optional[Any]:
    """Extract and parse JSON object or array from LLM response text."""
    if not text:
        return None
    # 1. Try direct markdown fence extraction
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(fence_pattern, text, re.IGNORECASE)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # 2. Try regex search for { ... } or [ ... ]
    json_candidate = re.search(r"(\{|\[)[\s\S]*(\}|\])", text)
    if json_candidate:
        try:
            return json.loads(json_candidate.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def match_job(job_description: str, index_job: bool = True) -> MatchResult:
    """
    1. Persists & indexes the job into Cognee under dataset 'jobs', node_set ['job'].
    2. Searches Qdrant for top candidate chunks (node_set ['cv']), grouping by candidate slug.
    3. Executes Cognee GRAPH_COMPLETION to extract reasoning, quotes, and fit scores.
    4. Combines measured cosine score with LLM fit score into a MatchResult.
    """
    # 1. Index job description if enabled
    if index_job:
        try:
            await cognee.add(
                job_description,
                dataset_name="jobs",
                node_set=["job"],
            )
            await cognee.cognify(datasets=["jobs"])
        except Exception as e:
            # Don't fail matching if job persistence has an error
            print(f"Warning: Failed to cognify job description: {e}")

    # 2. Vector search over candidate chunks
    engine = await get_vector_engine_async()
    try:
        raw_chunks = await engine.search(
            "DocumentChunk_text",
            job_description,
            limit=25,
            include_payload=True,
            node_name=["cv"],
        )
    except Exception as e:
        print(f"Error during vector chunk search: {e}")
        raw_chunks = []

    # Group chunks by candidate slug and take max score
    candidate_scores: Dict[str, Dict[str, Any]] = {}
    for chunk in raw_chunks:
        if not chunk.payload:
            continue
        belongs_to_set = chunk.payload.get("belongs_to_set", [])
        text_content = chunk.payload.get("text", "")
        
        # Find candidate slug tag (candidate:<slug>)
        candidate_tag = next((tag for tag in belongs_to_set if tag.startswith("candidate:")), None)
        if not candidate_tag:
            continue

        slug = candidate_tag.replace("candidate:", "")
        # The Qdrant adapter stores `1 - cosine_similarity` in chunk.score (i.e. cosine distance).
        # We convert it back to cosine similarity: (1.0 - chunk.score)
        raw_score = float(getattr(chunk, "score", 0.5))
        cosine_similarity = max(0.0, min(1.0, 1.0 - raw_score))
        score_pct = round(cosine_similarity * 100, 1)

        # Extract name from first line if available
        first_line = text_content.strip().split("\n")[0]
        extracted_name = first_line.replace("#", "").strip() if first_line.startswith("#") else slug.replace("_", " ").title()

        if slug not in candidate_scores or score_pct > candidate_scores[slug]["cosine_score"]:
            candidate_scores[slug] = {
                "name": extracted_name,
                "slug": slug,
                "cosine_score": score_pct,
                "top_chunk_text": text_content,
            }

    # Pick top 3 by measured cosine similarity (highest first)
    top_candidates = sorted(
        candidate_scores.values(),
        key=lambda c: c["cosine_score"],
        reverse=True,
    )[:3]

    if not top_candidates:
        return MatchResult(
            job_description=job_description,
            candidates=[],
            raw_graph_response="No matching candidate CVs found in the database.",
        )

    # 3. Graph completion reasoning over the CV knowledge graph
    candidate_names = ", ".join([c["name"] for c in top_candidates])
    graph_query = f"""You are an expert technical recruiter and HR evaluator.
Job Description:
\"\"\"{job_description}\"\"\"

Evaluate the fit of these top candidates from our knowledge graph: {candidate_names}.
Return a valid JSON array of objects with exactly this format:
```json
[
  {{
    "name": "Candidate Name",
    "fit_score": 90,
    "quotes": ["Exact quote from CV 1", "Exact quote from CV 2"],
    "reason": "Clear explanation of why this candidate fits the role requirements."
  }}
]
```
"""

    raw_graph_response_text = ""
    parsed_graph_data = None

    try:
        graph_results = await cognee.search(
            query_text=graph_query,
            query_type=cognee.SearchType.GRAPH_COMPLETION,
            datasets=["cvs"],
        )
        if graph_results:
            raw_graph_response_text = str(graph_results[0])
            parsed_graph_data = extract_json_block(raw_graph_response_text)
    except Exception as e:
        print(f"Error during GRAPH_COMPLETION search: {e}")
        raw_graph_response_text = f"Error during graph reasoning: {e}"

    # Map parsed graph data to candidates
    matched_candidates: List[CandidateMatch] = []
    
    parsed_list = []
    if isinstance(parsed_graph_data, list):
        parsed_list = parsed_graph_data
    elif isinstance(parsed_graph_data, dict):
        parsed_list = parsed_graph_data.get("candidates", [parsed_graph_data])

    parsed_by_name = {}
    for item in parsed_list:
        if isinstance(item, dict):
            name_key = item.get("name", "").lower().strip()
            if name_key:
                parsed_by_name[name_key] = item

    for cand_info in top_candidates:
        cand_name = cand_info["name"]
        cand_slug = cand_info["slug"]
        cosine_sc = cand_info["cosine_score"]

        # Look up LLM analysis by fuzzy name or slug match
        matched_llm_data = None
        for key, val in parsed_by_name.items():
            if key in cand_name.lower() or cand_name.lower() in key or cand_slug in key:
                matched_llm_data = val
                break

        if matched_llm_data:
            fit_sc = int(matched_llm_data.get("fit_score", int(cosine_sc)))
            quotes = matched_llm_data.get("quotes", [])
            reason = matched_llm_data.get("reason", "")
        else:
            fit_sc = int(cosine_sc)
            quotes = [cand_info.get("top_chunk_text", "")[:120] + "..."]
            reason = "Selected based on high semantic alignment with job requirements."

        matched_candidates.append(
            CandidateMatch(
                name=cand_name,
                slug=cand_slug,
                cosine_score=cosine_sc,
                fit_score=fit_sc,
                quotes=quotes,
                reason=reason,
                raw_snippet=cand_info.get("top_chunk_text"),
            )
        )

    return MatchResult(
        job_description=job_description,
        candidates=matched_candidates,
        raw_graph_response=raw_graph_response_text,
    )


if __name__ == "__main__":
    import sys
    test_jd = sys.argv[1] if len(sys.argv) > 1 else "Looking for a Senior Python backend engineer with FastAPI, Kafka, and distributed systems experience."
    print(f"Searching matches for:\n{test_jd}\n")
    res = asyncio.run(match_job(test_jd, index_job=False))
    print(f"\nFound {len(res.candidates)} candidates:")
    for c in res.candidates:
        print(f"\n👤 {c.name} (Cosine: {c.cosine_score}%, Fit: {c.fit_score}/100)")
        print(f"  Reason: {c.reason}")
        print(f"  Quotes:")
        for q in c.quotes:
            print(f"    - \"{q}\"")
