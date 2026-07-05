"""
graph.py — LangGraph StateGraph wiring the full multi-agent research pipeline.

Pipeline:
  planner → searcher → reader → writer → critic → [loop back to writer max 1x]
          → fact_checker → visualizer → END

The Critic→Writer loop is bounded to MAX_REVISIONS = 1.
"""
import asyncio
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from agents import (
    run_critic,
    run_fact_checker,
    run_planner,
    run_all_searches,
    run_reader,
    run_writer,
    run_visualizer,
)

logger = logging.getLogger(__name__)

MAX_REVISIONS = 1  # Hard cap on Critic→Writer retries


# --------------------------------------------------------------------------- #
# State definition
# --------------------------------------------------------------------------- #

class ResearchState(TypedDict, total=False):
    # Input
    topic: str

    # Pipeline state
    sub_questions: list[str]
    search_results: list[dict[str, Any]]
    source_chunks: list[dict[str, str]]
    report: str
    critic_scores: dict[str, Any]
    critic_feedback: str
    critic_missing_angles: list[str]    # ← angles the Critic flagged as absent
    revision_count: int
    fact_checked_report: str

    # Progress tracking (for SSE streaming)
    current_step: str

    # Output
    final_report: str
    sources: list[str]
    scores: dict[str, int]
    charts: list[dict[str, Any]]   # ← NEW: chart/table specs from Visualizer
    error: str


# --------------------------------------------------------------------------- #
# Node functions
# --------------------------------------------------------------------------- #

def planner_node(state: ResearchState) -> ResearchState:
    logger.info("=== PLANNER NODE ===")
    topic = state["topic"]
    sub_questions = run_planner(topic)
    return {
        **state,
        "sub_questions": sub_questions,
        "revision_count": 0,
        "current_step": "planning",
    }


def searcher_node(state: ResearchState) -> ResearchState:
    logger.info("=== SEARCHER NODE ===")
    sub_questions = state.get("sub_questions", [state["topic"]])

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run_all_searches(sub_questions))
                search_results = future.result(timeout=60)
        else:
            search_results = loop.run_until_complete(run_all_searches(sub_questions))
    except Exception:
        search_results = asyncio.run(run_all_searches(sub_questions))

    return {
        **state,
        "search_results": search_results,
        "current_step": "searching",
    }


def reader_node(state: ResearchState) -> ResearchState:
    logger.info("=== READER NODE ===")
    search_results = state.get("search_results", [])

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, run_reader(search_results))
                source_chunks = future.result(timeout=60)
        else:
            source_chunks = loop.run_until_complete(run_reader(search_results))
    except Exception:
        source_chunks = asyncio.run(run_reader(search_results))

    return {
        **state,
        "source_chunks": source_chunks,
        "current_step": "reading",
    }


def writer_node(state: ResearchState) -> ResearchState:
    logger.info("=== WRITER NODE (revision=%d) ===", state.get("revision_count", 0))
    topic = state["topic"]
    source_chunks = state.get("source_chunks", [])
    critic_feedback = state.get("critic_feedback", "")
    # Pass the structured missing-angles list on revision runs
    missing_angles = state.get("critic_missing_angles", []) if critic_feedback else []
    report = run_writer(topic, source_chunks, critic_feedback, missing_angles)
    return {
        **state,
        "report": report,
        "current_step": "writing",
    }


def critic_node(state: ResearchState) -> ResearchState:
    logger.info("=== CRITIC NODE ===")
    topic = state["topic"]
    report = state.get("report", "")
    scores = run_critic(topic, report)
    return {
        **state,
        "critic_scores": scores,
        "critic_feedback": scores.get("feedback", ""),
        "critic_missing_angles": scores.get("missing_angles", []),  # ← new
        "current_step": "reviewing",
    }


def fact_checker_node(state: ResearchState) -> ResearchState:
    logger.info("=== FACT-CHECKER NODE ===")
    report = state.get("report", "")
    source_chunks = state.get("source_chunks", [])
    fact_checked = run_fact_checker(report, source_chunks)

    # Collect all unique source URLs from chunks
    sources = list(
        dict.fromkeys(
            c["source_url"]
            for c in source_chunks
            if c.get("source_url") and not c.get("content", "").startswith("[")
        )
    )

    critic_scores = state.get("critic_scores", {})
    faithfulness = critic_scores.get("faithfulness", 0)
    completeness = critic_scores.get("completeness", 0)
    clarity      = critic_scores.get("clarity", 0)

    # Overall score — weighted average (out of 100%).
    # Weights reflect editorial priorities:
    #   40% faithfulness  — factual accuracy is paramount
    #   35% completeness  — coverage breadth is next most important
    #   25% clarity       — readability matters but is secondary
    # Formula: round((f*0.40 + c*0.35 + cl*0.25) * 10)
    overall_pct = round((faithfulness * 0.40 + completeness * 0.35 + clarity * 0.25) * 10)
    overall_pct = max(0, min(100, overall_pct))  # clamp to [0, 100]

    scores_out = {
        "faithfulness": faithfulness,
        "completeness": completeness,
        "clarity":      clarity,
        "overall_pct":  overall_pct,   # weighted composite, 0-100
    }

    return {
        **state,
        "fact_checked_report": fact_checked,
        "final_report": fact_checked,
        "sources": sources,
        "scores": scores_out,
        "current_step": "fact_checking",
    }


def visualizer_node(state: ResearchState) -> ResearchState:
    """Extract verifiable numeric data from sources → chart specs."""
    logger.info("=== VISUALIZER NODE ===")
    source_chunks = state.get("source_chunks", [])
    topic = state.get("topic", "")
    charts = run_visualizer(source_chunks, topic)
    return {
        **state,
        "charts": charts,
        "current_step": "visualizing",
    }


# --------------------------------------------------------------------------- #
# Conditional edge: should we loop back to writer?
# --------------------------------------------------------------------------- #

def should_revise(state: ResearchState) -> str:
    """
    Return 'writer' if we should loop back, or 'fact_checker' to proceed.
    Revision is triggered when:
      - faithfulness < 7  (factual problems)
      - OR completeness < 8  (threshold lowered from 7 so a 7/10 triggers one revision)
      - AND revision_count < MAX_REVISIONS

    The completeness threshold is intentionally higher (8) than faithfulness (7)
    because completeness consistently under-scores without targeted revision.
    """
    scores = state.get("critic_scores", {})
    revision_count = state.get("revision_count", 0)

    faithfulness = scores.get("faithfulness", 0)
    completeness = scores.get("completeness", 0)

    # Lower completeness threshold: < 8 now triggers revision (was < 7)
    needs_revision = (faithfulness < 7 or completeness < 8)

    if needs_revision and revision_count < MAX_REVISIONS:
        logger.info(
            "Critic: faithfulness=%d completeness=%d — looping back to writer (revision %d/%d)",
            faithfulness, completeness, revision_count + 1, MAX_REVISIONS,
        )
        return "writer"
    else:
        if needs_revision:
            logger.info(
                "Critic: faithfulness=%d completeness=%d — max revisions (%d) reached, proceeding.",
                faithfulness, completeness, MAX_REVISIONS,
            )
        else:
            logger.info(
                "Critic: faithfulness=%d completeness=%d — quality OK, proceeding to fact-checker.",
                faithfulness, completeness,
            )
        return "fact_checker"


def increment_revision(state: ResearchState) -> ResearchState:
    """Increment revision_count when looping back to writer."""
    return {**state, "revision_count": state.get("revision_count", 0) + 1}


# --------------------------------------------------------------------------- #
# Build graph
# --------------------------------------------------------------------------- #

def build_graph() -> Any:
    """Compile and return the research pipeline StateGraph."""
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("searcher", searcher_node)
    graph.add_node("reader", reader_node)
    graph.add_node("writer", writer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("increment_revision", increment_revision)
    graph.add_node("fact_checker", fact_checker_node)
    graph.add_node("visualizer", visualizer_node)   # ← NEW

    # Linear edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "reader")
    graph.add_edge("reader", "writer")
    graph.add_edge("writer", "critic")

    # Conditional edge after critic
    graph.add_conditional_edges(
        "critic",
        should_revise,
        {
            "writer": "increment_revision",
            "fact_checker": "fact_checker",
        },
    )
    graph.add_edge("increment_revision", "writer")
    graph.add_edge("fact_checker", "visualizer")   # ← NEW: fact_checker → visualizer
    graph.add_edge("visualizer", END)              # ← NEW: visualizer → END

    return graph.compile()


# Singleton compiled graph
research_graph = build_graph()


def run_research_pipeline(topic: str) -> ResearchState:
    """
    Execute the full research pipeline synchronously.
    Returns the final state dict.
    """
    initial_state: ResearchState = {
        "topic": topic,
        "revision_count": 0,
        "current_step": "starting",
    }
    result = research_graph.invoke(
        initial_state,
        config={
            "run_name": f"research: {topic[:60]}",
            "tags": ["production", "research-pipeline"],
            "metadata": {"topic": topic},
        },
    )
    return result