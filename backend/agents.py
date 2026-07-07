"""
agents.py — All LLM agent functions for the research pipeline.

Key design principles:
- SystemMessage carries fixed role definition (immutable from user input)
- User topic is always HumanMessage content, never string-concatenated into system
- Every LLM call has an explicit timeout
- Critic score parsing has guardrails with fallback to low score
"""
import asyncio
import json
import logging
import os
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from tools import tavily_search, scrape_urls

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# LLM clients — initialized lazily so tests can patch os.environ
# --------------------------------------------------------------------------- #
_GROQ_KEY_ENV = "GROQ_API_KEY"
LLM_TIMEOUT = 30  # seconds


def _get_large_llm() -> ChatGroq:
    """llama-3.3-70b-versatile for Planner, Writer, Critic."""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ.get(_GROQ_KEY_ENV, ""),
        temperature=0.3,
        max_tokens=4096,
        timeout=LLM_TIMEOUT,
    )


def _get_small_llm() -> ChatGroq:
    """llama-3.1-8b-instant for Fact-Checker — faster & cheaper."""
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.environ.get(_GROQ_KEY_ENV, ""),
        temperature=0.1,
        max_tokens=4096,
        timeout=LLM_TIMEOUT,
    )


# --------------------------------------------------------------------------- #
# Planner Agent
# --------------------------------------------------------------------------- #

# Coverage angles that the Planner must address when relevant.
# These are referenced by the Critic's 'missing' list and the Writer's revision instructions.
COVERAGE_ANGLES = [
    "current state / key statistics",
    "benefits / positive impacts",
    "risks / challenges",
    "expert or institutional opinions",
    "future outlook / predictions",
]


def run_planner(topic: str) -> list[str]:
    """
    Split the topic into 4-5 focused sub-questions covering the required angles.
    Always tries to include: current state, benefits, risks, expert opinions, future outlook.
    Returns a list of sub-question strings.
    """
    llm = _get_large_llm()
    angles_str = ", ".join(f"({i+1}) {a}" for i, a in enumerate(COVERAGE_ANGLES))
    messages = [
        SystemMessage(content=(
            "You are a Research Planner. Your task is to decompose a research topic into "
            "4 to 5 specific, non-overlapping sub-questions that give comprehensive coverage.\n\n"
            "You MUST include sub-questions that address each of these angles wherever relevant "
            f"to the topic: {angles_str}.\n\n"
            "Rules:\n"
            "1. Each sub-question must be directly answerable through web research.\n"
            "2. Questions must not overlap — each should cover a distinct angle.\n"
            "3. Tailor the questions to the specific topic; do not produce generic questions.\n"
            "4. Respond ONLY with a JSON array of strings, e.g.: "
            '["Question 1?", "Question 2?", "Question 3?", "Question 4?", "Question 5?"]. '
            "Do not include any other text, explanation, or markdown."
        )),
        HumanMessage(content=f"Research topic: {topic}"),
    ]
    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # Extract JSON array from response
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            questions = json.loads(match.group())
            questions = [q for q in questions if isinstance(q, str) and q.strip()]
            if 4 <= len(questions) <= 5:
                logger.info("Planner produced %d sub-questions for topic: %.60s", len(questions), topic)
                return questions
            # Also accept 3 if that's all we got
            if 3 <= len(questions):
                logger.warning("Planner returned %d sub-questions (expected 4-5). Proceeding.", len(questions))
                return questions[:5]
        logger.warning("Planner response couldn't be parsed cleanly, using fallback. Raw: %.120s", raw)
        lines = [l.strip().lstrip("0123456789.-) ") for l in raw.splitlines() if "?" in l]
        return lines[:5] if lines else [topic]
    except Exception as exc:
        logger.error("Planner agent failed: %s", exc)
        return [topic]


# --------------------------------------------------------------------------- #
# Search Agent
# --------------------------------------------------------------------------- #

async def run_search_agent(sub_question: str) -> dict[str, Any]:
    """Run Tavily search for one sub-question. Returns {question, results}."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, tavily_search, sub_question)
    return {"question": sub_question, "results": results}


async def run_all_searches(sub_questions: list[str]) -> list[dict[str, Any]]:
    """Run all sub-question searches in parallel."""
    tasks = [run_search_agent(q) for q in sub_questions]
    return await asyncio.gather(*tasks)


# --------------------------------------------------------------------------- #
# Reader Agent
# --------------------------------------------------------------------------- #

async def run_reader(search_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    For each sub-question's search results, scrape the top URLs in parallel.
    Returns a flat list of {source_url, content} chunks.
    """
    all_urls: list[str] = []
    seen: set[str] = set()
    for sr in search_results:
        for r in sr.get("results", []):
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                all_urls.append(url)

    if not all_urls:
        logger.warning("Reader agent: no URLs to scrape.")
        return []

    # Scrape up to 5 URLs per sub-question (capped at 20 total for speed)
    all_urls = all_urls[:20]
    chunks = await scrape_urls(all_urls)
    # Filter out failed chunks
    good_chunks = [c for c in chunks if not c["content"].startswith("[")]
    logger.info("Reader scraped %d/%d URLs successfully.", len(good_chunks), len(all_urls))
    return chunks  # Return all (including failures) so Writer knows what was attempted


# --------------------------------------------------------------------------- #
# Writer Agent
# --------------------------------------------------------------------------- #

def run_writer(
    topic: str,
    source_chunks: list[dict[str, str]],
    critic_feedback: str = "",
    missing_angles: list[str] | None = None,
) -> str:
    """
    Draft a comprehensive markdown report from tagged source material.
    On revision, critic_feedback and missing_angles guide targeted improvements.

    missing_angles: list of coverage angles (from COVERAGE_ANGLES) that the Critic
    identified as absent. The Writer must add dedicated sections for each one.
    """
    llm = _get_large_llm()

    # Build source material context (truncated to avoid token overflow)
    source_text_parts = []
    for chunk in source_chunks:
        url = chunk.get("source_url", "unknown")
        content = chunk.get("content", "")
        if content and not content.startswith("["):
            source_text_parts.append(f"[Source: {url}]\n{content[:3000]}")

    source_context = "\n\n---\n\n".join(source_text_parts[:12])  # max 12 chunks

    # Build revision instructions block
    feedback_section = ""
    if critic_feedback:
        revision_lines = ["## Revision Instructions from Critic", critic_feedback]

        if missing_angles:
            angles_list = "\n".join(f"  - {a}" for a in missing_angles)
            revision_lines.append(
                f"\n## Missing Coverage — You MUST add dedicated sections for:\n{angles_list}\n"
                "For each missing angle above:\n"
                "  • Add a ## or ### heading named after the angle.\n"
                "  • Write at least 2 substantive paragraphs using the source material.\n"
                "  • Cite every fact inline as [Source: URL].\n"
                "  • If the source material has no content for an angle, note it briefly "
                "rather than omitting the section entirely."
            )

        feedback_section = "\n\n" + "\n".join(revision_lines) + "\n"

    is_revision = bool(critic_feedback)

    system_msg = SystemMessage(content=(
        "You are an expert Research Writer. Your task is to synthesize provided source material "
        "into a well-structured, comprehensive markdown report.\n\n"
        "Rules:\n"
        "1. Only use information from the provided source material — do not invent facts.\n"
        "2. Structure with clear headings (## and ###). Cover ALL of: current state/statistics, "
        "benefits, risks/challenges, expert or institutional opinions, and future outlook — "
        "even if some sections are brief due to limited sources.\n"
        "3. Include an ## Executive Summary at the top.\n"
        "4. Be specific, accurate, and cite sources inline as [Source: URL].\n"
        + ("5. This is a REVISION — address EVERY point in the revision instructions below, "
           "especially any missing angles explicitly listed.\n" if is_revision else "")
        + "6. End with a ## Conclusion section.\n"
        "Do not add disclaimers or meta-commentary about the writing process."
    ))
    human_msg = HumanMessage(content=(
        f"Research Topic: {topic}"
        f"{feedback_section}"
        f"\n\n## Source Material\n\n{source_context}"
    ))

    try:
        response = llm.invoke([system_msg, human_msg])
        report = response.content.strip()
        logger.info(
            "Writer produced report of %d chars (revision=%s, missing=%s).",
            len(report), is_revision, missing_angles,
        )
        return report
    except Exception as exc:
        logger.error("Writer agent failed: %s", exc)
        return f"# Research Report: {topic}\n\n[Report generation failed: {exc}]"


# --------------------------------------------------------------------------- #
# Critic Agent
# --------------------------------------------------------------------------- #

def _parse_score(raw: str, field: str) -> int:
    """
    Extract an integer 0-10 from a string like 'faithfulness: 8'.
    Returns 0 (low score) if parsing fails, so the pipeline retries safely.
    """
    pattern = re.compile(rf"{field}[\s:]*(\d+)", re.IGNORECASE)
    match = pattern.search(raw)
    if match:
        val = int(match.group(1))
        if 0 <= val <= 10:
            return val
    logger.warning("Could not parse '%s' score from critic output. Defaulting to 0.", field)
    return 0


def _parse_missing_angles(raw: str) -> list[str]:
    """
    Parse the 'Missing: ["angle 1", "angle 2"]' line from critic output.
    Returns a list of strings, or [] if absent/unparseable.
    """
    match = re.search(r"Missing:\s*(\[.*?\])", raw, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    try:
        angles = json.loads(match.group(1))
        if isinstance(angles, list):
            return [str(a).strip() for a in angles if str(a).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def run_critic(topic: str, report: str) -> dict[str, Any]:
    """
    Score the report on faithfulness, completeness, and clarity (each 0-10).
    When completeness < 8, also emits a 'Missing' list of coverage angles.
    Returns {faithfulness, completeness, clarity, feedback, missing_angles}.
    Parse errors default to 0 (triggers revision).
    """
    llm = _get_large_llm()
    angles_str = ", ".join(f'"{a}"' for a in COVERAGE_ANGLES)
    system_msg = SystemMessage(content=(
        "You are a rigorous Research Critic. Evaluate the provided research report on three dimensions:\n"
        "1. Faithfulness (0-10): Are all claims supported by cited sources? No hallucinations?\n"
        "2. Completeness (0-10): Does the report thoroughly cover the topic, including: "
        "current state/statistics, benefits, risks/challenges, expert or institutional opinions, "
        "and future outlook?\n"
        "3. Clarity (0-10): Is the report well-structured and easy to understand?\n\n"
        "Respond in EXACTLY this format (integers only for scores):\n"
        "Faithfulness: <score>\n"
        "Completeness: <score>\n"
        "Clarity: <score>\n"
        "Feedback: <specific actionable feedback for the writer, or 'None' if all scores >= 8>\n"
        "Missing: <if completeness < 8, a JSON array of missing coverage angles chosen ONLY from "
        f"[{angles_str}], e.g. [\"expert or institutional opinions\", \"future outlook / predictions\"]. "
        "If completeness >= 8, write Missing: []>"
    ))
    human_msg = HumanMessage(content=(
        f"Research Topic: {topic}\n\n## Report to Evaluate\n\n{report[:6000]}"
    ))

    try:
        response = llm.invoke([system_msg, human_msg])
        raw = response.content.strip()
        faithfulness = _parse_score(raw, "faithfulness")
        completeness = _parse_score(raw, "completeness")
        clarity = _parse_score(raw, "clarity")

        # Extract general feedback
        feedback_match = re.search(r"feedback:\s*(.+?)(?=\nmissing:|$)", raw, re.IGNORECASE | re.DOTALL)
        feedback = feedback_match.group(1).strip() if feedback_match else ""

        # Extract structured missing-angles list
        missing_angles = _parse_missing_angles(raw)

        logger.info(
            "Critic scores — faithfulness:%d completeness:%d clarity:%d missing=%s",
            faithfulness, completeness, clarity, missing_angles,
        )
        return {
            "faithfulness": faithfulness,
            "completeness": completeness,
            "clarity": clarity,
            "feedback": feedback,
            "missing_angles": missing_angles,
        }
    except Exception as exc:
        logger.error("Critic agent failed: %s. Defaulting to low scores.", exc)
        return {
            "faithfulness": 0,
            "completeness": 0,
            "clarity": 0,
            "feedback": f"Critic evaluation failed ({exc}). Please revise for accuracy and completeness.",
            "missing_angles": list(COVERAGE_ANGLES),  # assume all missing on error
        }


# --------------------------------------------------------------------------- #
# Fact-Checker Agent
# --------------------------------------------------------------------------- #

def run_fact_checker(report: str, source_chunks: list[dict[str, str]]) -> str:
    """
    Cross-check every claim in the report against source chunks.
    Insert inline [Source: URL] citations. Flag or remove unsupported claims.
    Uses a smaller/faster model.
    """
    llm = _get_small_llm()

    source_text_parts = []
    for chunk in source_chunks:
        url = chunk.get("source_url", "unknown")
        content = chunk.get("content", "")
        if content and not content.startswith("["):
            source_text_parts.append(f"[Source: {url}]\n{content[:2000]}")

    source_context = "\n\n---\n\n".join(source_text_parts[:10])

    system_msg = SystemMessage(content=(
        "You are a meticulous Fact-Checker. Your task:\n"
        "1. Read the research report and the source material.\n"
        "2. For each factual claim in the report, verify it is supported by a source.\n"
        "3. Add inline citations '[Source: URL]' immediately after supported claims.\n"
        "4. If a claim is NOT supported by any source, prepend it with '[UNVERIFIED] '.\n"
        "5. Do NOT change the report's structure, headings, or writing style.\n"
        "6. Return the complete fact-checked report in markdown.\n"
        "Do not add any preamble or explanation — return ONLY the markdown report."
    ))
    human_msg = HumanMessage(content=(
        f"## Report to Fact-Check\n\n{report}\n\n"
        f"## Source Material\n\n{source_context}"
    ))

    try:
        response = llm.invoke([system_msg, human_msg])
        fact_checked = response.content.strip()
        logger.info("Fact-checker produced report of %d chars.", len(fact_checked))
        return fact_checked
    except Exception as exc:
        logger.error("Fact-checker agent failed: %s. Returning original report.", exc)
        return report  # Graceful fallback: return unmodified report


# --------------------------------------------------------------------------- #
# Visualizer Agent
# --------------------------------------------------------------------------- #

def _validate_chart_data(
    charts: list[dict[str, Any]],
    source_chunks: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Cross-check every numeric value in each chart against the raw source text.
    A data point is accepted only if its value (as a string) literally appears
    in the corresponding source chunk text. Points that can't be traced are dropped.
    Charts with no valid data points after validation are dropped entirely.
    """
    # Build a lookup: source_url → full text
    source_map: dict[str, str] = {}
    for chunk in source_chunks:
        url = chunk.get("source_url", "")
        if url:
            source_map[url] = chunk.get("content", "")

    # Also build a combined text for charts without a specific source_url
    all_text = " ".join(source_map.values())

    validated = []
    for chart in charts:
        source_url = chart.get("source_url", "")
        search_text = source_map.get(source_url, all_text)

        valid_points = []
        for point in chart.get("data", []):
            raw_val = point.get("value")
            if raw_val is None:
                continue
            # Check if the value (as int, float, or string) appears literally
            val_str = str(raw_val).rstrip("0").rstrip(".")  # normalise floats
            if val_str and val_str in search_text:
                valid_points.append(point)
            else:
                logger.debug(
                    "Visualizer: dropping unverified value %s for label '%s'",
                    raw_val, point.get("label", "?"),
                )

        if valid_points:
            validated.append({**chart, "data": valid_points})
        else:
            logger.info("Visualizer: chart '%s' had no verifiable data — dropped.", chart.get("title", "?"))

    return validated


def run_visualizer(
    source_chunks: list[dict[str, str]],
    topic: str,
) -> list[dict[str, Any]]:
    """
    Extract genuine numeric data from source-tagged chunks and produce
    chart/stat/table specifications. Never invents numbers.

    Output types:
      "stat"  — a single, isolated number (headline figure).
      "bar"   — 2+ values suitable for a comparative bar chart.
      "line"  — 2+ values forming a time/trend series.
      "table" — mixed or multi-column data presented as rows.

    Returns a validated list of chart dicts (up to 12), or [] if nothing found.
    """
    llm = _get_small_llm()

    # Use up to 12 source chunks for better data coverage
    source_parts = []
    for chunk in source_chunks:
        url = chunk.get("source_url", "unknown")
        content = chunk.get("content", "")
        if content and not content.startswith("["):
            source_parts.append(f"[Source: {url}]\n{content[:2500]}")

    if not source_parts:
        logger.info("Visualizer: no source content to extract data from.")
        return []

    source_context = "\n\n---\n\n".join(source_parts[:12])

    system_msg = SystemMessage(content=(
        "You are a Data Extraction Specialist. Your ONLY job is to find genuine numeric data "
        "that is EXPLICITLY stated verbatim in the provided source text — never infer, estimate, or invent numbers.\n\n"

        "CRITICAL TYPE RULES — choose the correct type for each piece of data:\n\n"

        "  \"stat\" — Use this for a SINGLE isolated number (e.g. '$13 trillion global economic impact', '40% of jobs at risk').\n"
        "            A single number with no comparator group is ALWAYS a stat, never a bar/line chart.\n"
        "            data must have exactly ONE entry: [{\"label\": \"<descriptive label>\", \"value\": <number>}]\n\n"

        "  \"bar\"  — Use this ONLY when you have 2 or more comparable values for DIFFERENT categories.\n"
        "            Example: job displacement rates across 5 industries = 5 bars.\n"
        "            data must have 2+ entries, each with a different label.\n\n"

        "  \"line\" — Use this ONLY when you have 2 or more values across TIME points (years, quarters, months).\n"
        "            Example: AI investment in 2020, 2021, 2022, 2023 = 4 line points.\n"
        "            data must have 2+ entries ordered chronologically.\n\n"

        "  \"table\" — Use this when you have multi-column structured data (rows with more than one attribute),\n"
        "             or when bar/line doesn't fit cleanly.\n"
        "             data must have 2+ entries.\n\n"

        "Additional rules:\n"
        "- Extract ONLY numbers that appear verbatim in the source text.\n"
        "- Set source_url to the exact URL the numbers came from.\n"
        "- If NO genuine numeric data exists in the sources, return [].\n"
        "- DO NOT fabricate charts, stats, or numbers to fill space.\n"
        "- Prefer fewer accurate stats over many invented ones.\n\n"

        "Output ONLY valid JSON (no markdown fences, no explanation):\n"
        "[\n"
        "  {\"type\": \"stat\",  \"title\": \"...\", \"unit\": \"...\", \"source_url\": \"...\", "
        "\"data\": [{\"label\": \"...\", \"value\": <number>}]},\n"
        "  {\"type\": \"bar\",  \"title\": \"...\", \"unit\": \"...\", \"source_url\": \"...\", "
        "\"data\": [{\"label\": \"...\", \"value\": <number>}, ...]},\n"
        "  {\"type\": \"line\", \"title\": \"...\", \"unit\": \"...\", \"source_url\": \"...\", "
        "\"data\": [{\"label\": \"2020\", \"value\": <number>}, ...]},\n"
        "  {\"type\": \"table\",\"title\": \"...\", \"unit\": \"...\", \"source_url\": \"...\", "
        "\"data\": [{\"label\": \"...\", \"value\": <number>}, ...]}\n"
        "]"
    ))
    human_msg = HumanMessage(content=(
        f"Research topic: {topic}\n\n"
        f"Source material to scan for numeric data:\n\n{source_context}"
    ))

    try:
        response = llm.invoke([system_msg, human_msg])
        raw = response.content.strip()

        # Extract JSON array (model may wrap in markdown fences)
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not json_match:
            logger.info("Visualizer: no JSON array found in LLM response.")
            return []

        charts = json.loads(json_match.group())
        if not isinstance(charts, list):
            logger.warning("Visualizer: parsed JSON is not a list.")
            return []

        # Enforce type field is valid
        valid_types = {"stat", "bar", "line", "table"}
        charts = [c for c in charts if isinstance(c, dict) and c.get("type") in valid_types]

        # Validate: drop data points whose numeric value isn't literally in source text
        validated = _validate_chart_data(charts, source_chunks)
        logger.info(
            "Visualizer: LLM returned %d charts → %d passed validation.",
            len(charts), len(validated),
        )
        return validated

    except json.JSONDecodeError as exc:
        logger.warning("Visualizer: JSON parse failed: %s. Returning empty.", exc)
        return []
    except Exception as exc:
        logger.error("Visualizer agent failed: %s. Returning empty.", exc)
        return []


# --------------------------------------------------------------------------- #
# Summarizer (used by /summarize endpoint — not part of the main graph)
# --------------------------------------------------------------------------- #

def run_summarizer(report: str, length: str = "brief") -> str:
    """
    Produce a bullet-point summary of the finished report.
    length: 'brief' = 3 bullets, 'detailed' = 7 bullets.
    Uses the small fast model — it's a lightweight compression task.
    """
    llm = _get_small_llm()
    bullet_count = 7 if length == "detailed" else 3

    system_msg = SystemMessage(content=(
        f"You are a precise Research Summarizer. Your task is to distill the provided "
        f"research report into exactly {bullet_count} bullet points.\n\n"
        "Rules:\n"
        "1. Summarize ONLY information already present in the report — do not add new claims.\n"
        "2. Do NOT introduce any number, statistic, or fact not explicitly stated in the report.\n"
        "3. Each bullet must be a single, complete sentence starting with '• '.\n"
        "4. Cover the most important findings, ordered by significance.\n"
        "5. Return ONLY the bullet points — no title, no preamble, no extra text."
    ))
    human_msg = HumanMessage(content=(
        f"Research report to summarize:\n\n{report[:8000]}"
    ))

    try:
        response = llm.invoke([system_msg, human_msg])
        summary = response.content.strip()
        logger.info("Summarizer produced %d chars.", len(summary))
        return summary
    except Exception as exc:
        logger.error("Summarizer failed: %s", exc)
        return "• Summary generation failed. Please try again."
