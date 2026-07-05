"""
main.py — FastAPI application: /research endpoint with SSE streaming,
rate limiting (slowapi), CORS, and Pydantic v2 validation.
No API keys are ever returned in responses.
"""
import json
import logging
import os

# Load .env FIRST — before any other module reads os.environ
from dotenv import load_dotenv
load_dotenv()  # reads backend/.env automatically
import time
import concurrent.futures
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from security import validate_input

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
limiter = Limiter(key_func=get_remote_address, default_limits=["5/minute"])


# --------------------------------------------------------------------------- #
# App lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Research Assistant API starting up.")
    yield
    logger.info("Research Assistant API shutting down.")


app = FastAPI(
    title="Multi-Agent Research Assistant",
    description="LangGraph-powered research pipeline with Groq LLM and Tavily search.",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --------------------------------------------------------------------------- #
# CORS — production restricts to deployed frontend origin
# --------------------------------------------------------------------------- #
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# --------------------------------------------------------------------------- #
# Pydantic v2 models
# --------------------------------------------------------------------------- #
class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300, description="Research topic")

    @field_validator("topic")
    @classmethod
    def topic_must_be_safe(cls, v: str) -> str:
        from security import validate_input
        try:
            return validate_input(v)
        except ValueError as e:
            raise ValueError(str(e)) from e


class CriticScores(BaseModel):
    faithfulness: int = Field(ge=0, le=10)
    completeness: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)


class ResearchResponse(BaseModel):
    topic: str
    report: str
    scores: CriticScores
    sources: list[str]
    revision_count: int
    elapsed_seconds: float


# --------------------------------------------------------------------------- #
# SSE helper
# --------------------------------------------------------------------------- #
def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


STEP_LABELS = {
    "starting":      "Initializing pipeline",
    "planning":      "Planning research sub-questions",
    "searching":     "Searching the web",
    "reading":       "Reading and extracting sources",
    "writing":       "Writing the report",
    "reviewing":     "Reviewing for quality",
    "fact_checking": "Fact-checking and citing sources",
    "visualizing":   "Extracting data for charts",
    "done":          "Report ready",
}


# --------------------------------------------------------------------------- #
# Research endpoint
# --------------------------------------------------------------------------- #
@app.post("/research")
@limiter.limit("5/minute")
async def research(request: Request, body: ResearchRequest) -> StreamingResponse:
    """
    Stream research pipeline progress via Server-Sent Events.
    Final event contains the complete report.
    """
    import concurrent.futures
    import asyncio

    topic = body.topic

    async def event_stream() -> AsyncIterator[str]:
        start_time = time.time()

        # Import graph here to allow monkeypatching in tests
        from graph import run_research_pipeline

        yield _sse_event("progress", {"step": "starting", "label": STEP_LABELS["starting"]})

        # Run the blocking pipeline in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:

            # We can't stream intermediate steps from the blocking pipeline easily,
            # so we yield synthetic progress events at timed intervals while running.
            steps_sequence = ["planning", "searching", "reading", "writing", "reviewing", "fact_checking"]
            step_idx = 0

            future = loop.run_in_executor(pool, run_research_pipeline, topic)

            # Yield progress events roughly every 3 seconds while pipeline runs
            while not future.done():
                if step_idx < len(steps_sequence):
                    step = steps_sequence[step_idx]
                    yield _sse_event("progress", {
                        "step": step,
                        "label": STEP_LABELS.get(step, step),
                    })
                    step_idx += 1
                await asyncio.sleep(3)

            try:
                result = await future
            except Exception as exc:
                logger.error("Pipeline failed for topic %.60s: %s", topic, exc)
                yield _sse_event("error", {"message": "Research pipeline encountered an error. Please try again."})
                return

        elapsed = time.time() - start_time

        # Validate and build final response (no secrets in output)
        # Scoring weights: faithfulness 40%, completeness 35%, clarity 25%
        # (same formula as graph.py fact_checker_node)
        scores_raw = result.get("scores", {})
        scores = {
            "faithfulness": max(0, min(10,  int(scores_raw.get("faithfulness", 0)))),
            "completeness": max(0, min(10,  int(scores_raw.get("completeness", 0)))),
            "clarity":      max(0, min(10,  int(scores_raw.get("clarity", 0)))),
            "overall_pct":  max(0, min(100, int(scores_raw.get("overall_pct", 0)))),
        }

        final_data = {
            "topic": topic,
            "report": result.get("final_report", result.get("report", "[No report generated]")),
            "scores": scores,
            "sources": result.get("sources", []),
            "charts": result.get("charts", []),   # ← NEW
            "revision_count": result.get("revision_count", 0),
            "elapsed_seconds": round(elapsed, 2),
        }

        yield _sse_event("progress", {"step": "done", "label": STEP_LABELS["done"]})
        yield _sse_event("result", final_data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------------------- #
# Health check
# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


# --------------------------------------------------------------------------- #
# Summarize endpoint
# --------------------------------------------------------------------------- #
class SummarizeRequest(BaseModel):
    report: str = Field(..., min_length=50, max_length=20_000, description="Report text to summarize")
    length: str = Field(default="brief", description="'brief' (3 bullets) or 'detailed' (7 bullets)")

    @field_validator("report")
    @classmethod
    def report_must_be_safe(cls, v: str) -> str:
        from security import validate_input
        try:
            # Sanitize but allow longer text — override length for report body
            import re as _re
            # Only run injection check, not length check (report can be long)
            from security import check_prompt_injection
            check_prompt_injection(v)
            return v.strip()
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("length")
    @classmethod
    def length_must_be_valid(cls, v: str) -> str:
        if v not in ("brief", "detailed"):
            return "brief"  # safe default instead of rejecting
        return v


@app.post("/summarize")
@limiter.limit("5/minute")   # same rate limit as /research
async def summarize(request: Request, body: SummarizeRequest) -> dict:
    """
    Return a 3-5 bullet summary (brief) or 7 bullet summary (detailed)
    of the provided research report. All bullets are derived ONLY from
    the input text — the model is instructed not to add new claims.
    """
    from agents import run_summarizer

    loop = asyncio.get_event_loop()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            summary = await loop.run_in_executor(
                pool, run_summarizer, body.report, body.length
            )
    except Exception as exc:
        logger.error("Summarizer endpoint failed: %s", exc)
        raise HTTPException(status_code=500, detail="Summary generation failed. Please try again.")

    return {"summary": summary, "length": body.length}


# --------------------------------------------------------------------------- #
# Validation error handler — returns 400 on bad input
# --------------------------------------------------------------------------- #
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = [e.get("msg", "Validation error") for e in errors]
    return JSONResponse(
        status_code=400,
        content={"detail": "; ".join(messages)},
    )
