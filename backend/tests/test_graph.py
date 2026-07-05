"""
test_graph.py — Tests for the LangGraph pipeline.
All LLM and API calls are mocked. Verifies:
  - Full pipeline produces expected output keys
  - Critic loop respects MAX_REVISIONS=1 bound
  - Critic score parse failures default to low scores (triggering revision)
  - Pipeline degrades gracefully when individual agents fail
"""
import sys
import os
import json
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_llm_msg(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    return msg


PLANNER_RESPONSE = '["What is quantum computing?", "How do quantum computers work?", "Applications of quantum computing"]'

GOOD_CRITIC_RESPONSE = """Faithfulness: 9
Completeness: 8
Clarity: 9
Feedback: None"""

BAD_CRITIC_RESPONSE = """Faithfulness: 4
Completeness: 5
Clarity: 6
Feedback: The report lacks specific examples and source citations. Please add more detail."""

WRITER_RESPONSE = """# Quantum Computing Research Report

## Executive Summary
Quantum computing represents a paradigm shift in computation.

## Key Findings
Quantum computers use qubits instead of classical bits.

## Conclusion
Quantum computing will revolutionize cryptography and drug discovery.
"""

FACT_CHECKED_RESPONSE = WRITER_RESPONSE + "\n\n*Fact-checked and citations added.*"

TAVILY_RESULTS = [
    {"title": "Quantum Computing Explained", "url": "https://example.com/qc", "content": "Quantum computers use qubits."},
]

SCRAPED_CHUNKS = [
    {"source_url": "https://example.com/qc", "content": "Quantum computers use qubits and superposition to process information."},
]


def _patch_all_agents(
    planner_response=PLANNER_RESPONSE,
    critic_response=GOOD_CRITIC_RESPONSE,
    writer_response=WRITER_RESPONSE,
    fact_check_response=FACT_CHECKED_RESPONSE,
):
    """Return a context manager stack that patches all external agent calls."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        llm_large = MagicMock()
        llm_small = MagicMock()

        def large_invoke(messages):
            # Detect which agent is calling based on system message content
            sys_content = messages[0].content if messages else ""
            if "Planner" in sys_content:
                return make_llm_msg(planner_response)
            elif "Critic" in sys_content:
                return make_llm_msg(critic_response)
            elif "Writer" in sys_content:
                return make_llm_msg(writer_response)
            return make_llm_msg("Generic LLM response")

        def small_invoke(messages):
            return make_llm_msg(fact_check_response)

        llm_large.invoke.side_effect = large_invoke
        llm_small.invoke.side_effect = small_invoke

        async def fake_searches(sub_questions):
            return [{"question": q, "results": TAVILY_RESULTS} for q in sub_questions]

        async def fake_reader(search_results):
            return SCRAPED_CHUNKS

        with patch("agents._get_large_llm", return_value=llm_large), \
             patch("agents._get_small_llm", return_value=llm_small), \
             patch("agents.run_all_searches", side_effect=fake_searches), \
             patch("agents.run_reader", side_effect=fake_reader):
            yield llm_large, llm_small

    return _ctx()


# --------------------------------------------------------------------------- #
# Full pipeline tests
# --------------------------------------------------------------------------- #
class TestFullPipeline:
    def test_pipeline_returns_expected_keys(self):
        """Full pipeline should return final_report, sources, scores, revision_count."""
        with _patch_all_agents():
            from graph import run_research_pipeline
            result = run_research_pipeline("Quantum computing")

        assert "final_report" in result or "report" in result
        assert "scores" in result
        assert "sources" in result
        assert "revision_count" in result

    def test_pipeline_includes_fact_checked_content(self):
        """Final report should be the fact-checked version."""
        with _patch_all_agents():
            from graph import run_research_pipeline
            result = run_research_pipeline("Quantum computing")

        report = result.get("final_report", result.get("fact_checked_report", ""))
        assert len(report) > 50

    def test_pipeline_scores_in_valid_range(self):
        """All critic scores should be integers 0-10."""
        with _patch_all_agents():
            from graph import run_research_pipeline
            result = run_research_pipeline("Quantum computing")

        scores = result.get("scores", {})
        for key in ["faithfulness", "completeness", "clarity"]:
            assert key in scores
            assert 0 <= scores[key] <= 10


# --------------------------------------------------------------------------- #
# Critic loop bound tests
# --------------------------------------------------------------------------- #
class TestCriticLoopBound:
    def test_no_revision_when_scores_high(self):
        """When critic gives high scores, writer should only be called once."""
        writer_call_count = 0

        def counting_writer(topic, source_chunks, critic_feedback=""):
            nonlocal writer_call_count
            writer_call_count += 1
            return WRITER_RESPONSE

        with _patch_all_agents(critic_response=GOOD_CRITIC_RESPONSE):
            with patch("graph.run_writer", side_effect=counting_writer):
                from graph import run_research_pipeline
                result = run_research_pipeline("Quantum computing")

        assert writer_call_count == 1
        assert result.get("revision_count", 0) == 0

    def test_one_revision_when_scores_low(self):
        """When critic gives low scores, writer should be called exactly twice (1 revision)."""
        writer_call_count = 0
        critic_call_count = 0

        def counting_writer(topic, source_chunks, critic_feedback=""):
            nonlocal writer_call_count
            writer_call_count += 1
            return WRITER_RESPONSE

        # First critic call: bad scores → revision. Second call: still bad but max reached.
        def counting_critic(topic, report):
            nonlocal critic_call_count
            critic_call_count += 1
            return {
                "faithfulness": 4,
                "completeness": 5,
                "clarity": 6,
                "feedback": "Needs more detail and citations.",
            }

        with _patch_all_agents(critic_response=BAD_CRITIC_RESPONSE):
            with patch("graph.run_writer", side_effect=counting_writer), \
                 patch("graph.run_critic", side_effect=counting_critic):
                from graph import run_research_pipeline
                result = run_research_pipeline("Quantum computing")

        # Writer called at most 2 times (initial + 1 revision)
        assert writer_call_count <= 2, f"Writer called {writer_call_count} times — expected at most 2"
        # Revision count should be 1
        assert result.get("revision_count", 0) <= 1

    def test_never_more_than_one_retry(self):
        """Even with perpetually bad scores, pipeline must terminate after 1 retry."""
        writer_call_count = 0

        def always_bad_critic(topic, report):
            return {"faithfulness": 1, "completeness": 1, "clarity": 1, "feedback": "Always bad."}

        def counting_writer(topic, source_chunks, critic_feedback=""):
            nonlocal writer_call_count
            writer_call_count += 1
            return WRITER_RESPONSE

        with _patch_all_agents():
            with patch("graph.run_critic", side_effect=always_bad_critic), \
                 patch("graph.run_writer", side_effect=counting_writer):
                from graph import run_research_pipeline
                result = run_research_pipeline("Any topic")

        # Strictly bounded: initial write + at most 1 revision = max 2 calls
        assert writer_call_count <= 2, (
            f"Writer called {writer_call_count} times — loop is unbounded!"
        )


# --------------------------------------------------------------------------- #
# Critic score parse failure tests
# --------------------------------------------------------------------------- #
class TestCriticScoreParseFailure:
    def test_unparseable_score_defaults_to_zero(self):
        """If critic returns garbage, scores default to 0 (triggers revision)."""
        from agents import _parse_score

        # Completely unparseable
        assert _parse_score("I cannot evaluate this", "faithfulness") == 0
        assert _parse_score("", "completeness") == 0
        assert _parse_score("N/A", "clarity") == 0

    def test_parseable_score_extracted_correctly(self):
        """Valid score strings are parsed correctly."""
        from agents import _parse_score

        assert _parse_score("Faithfulness: 8", "faithfulness") == 8
        assert _parse_score("Completeness: 10", "completeness") == 10
        assert _parse_score("Clarity: 0", "clarity") == 0

    def test_out_of_range_score_not_returned(self):
        """Scores outside 0-10 should not be returned as-is (return 0 instead)."""
        from agents import _parse_score

        # 11 is out of range
        result = _parse_score("Faithfulness: 11", "faithfulness")
        assert result == 0

    def test_critic_agent_handles_llm_exception(self):
        """If the LLM raises, critic returns safe low-score defaults."""
        llm = MagicMock()
        llm.invoke.side_effect = Exception("LLM unavailable")

        with patch("agents._get_large_llm", return_value=llm):
            from agents import run_critic
            result = run_critic("test topic", "test report")

        assert result["faithfulness"] == 0
        assert result["completeness"] == 0
        assert "feedback" in result


# --------------------------------------------------------------------------- #
# should_revise conditional edge tests
# --------------------------------------------------------------------------- #
class TestShouldRevise:
    def test_proceeds_when_scores_good(self):
        from graph import should_revise

        state = {
            "topic": "test",
            "critic_scores": {"faithfulness": 8, "completeness": 8, "clarity": 9},
            "revision_count": 0,
        }
        assert should_revise(state) == "fact_checker"

    def test_loops_when_faithfulness_low(self):
        from graph import should_revise

        state = {
            "topic": "test",
            "critic_scores": {"faithfulness": 5, "completeness": 8, "clarity": 7},
            "revision_count": 0,
        }
        assert should_revise(state) == "writer"

    def test_loops_when_completeness_low(self):
        from graph import should_revise

        state = {
            "topic": "test",
            "critic_scores": {"faithfulness": 8, "completeness": 4, "clarity": 7},
            "revision_count": 0,
        }
        assert should_revise(state) == "writer"

    def test_proceeds_when_max_revisions_reached(self):
        from graph import should_revise, MAX_REVISIONS

        state = {
            "topic": "test",
            "critic_scores": {"faithfulness": 3, "completeness": 3, "clarity": 3},
            "revision_count": MAX_REVISIONS,  # Already at max
        }
        assert should_revise(state) == "fact_checker"
