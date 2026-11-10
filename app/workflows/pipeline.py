
"""LangGraph workflow for AI-powered product enrichment with human review."""

import sqlite3
import uuid
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt, Command

from app.core.config import settings
from app.schemas import ProductInput
from app.services.normalizer import normalize
from app.services.extractor import extract_attributes
from app.services.taxonomy import map_category
from app.services.llm import generate_seo
from app.services.validator import validate


# --------------------------------------------------
# 1. Persistent workflow checkpoint storage
# --------------------------------------------------

CHECKPOINT_DB = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "langgraph_checkpoints.db"
)

CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)

checkpoint_connection = sqlite3.connect(
    str(CHECKPOINT_DB),
    check_same_thread=False
)

checkpointer = SqliteSaver(checkpoint_connection)
checkpointer.setup()


# --------------------------------------------------
# 2. Shared workflow state
# --------------------------------------------------

class PipelineState(TypedDict, total=False):
    product: dict[str, Any]
    data: dict[str, Any]
    validation_errors: list[str]
    retries: int
    status: str
    reviewer_notes: str


# --------------------------------------------------
# 3. Workflow nodes
# --------------------------------------------------

def normalize_node(state: PipelineState) -> dict:
    data = normalize(state["product"])
    return {"data": data}


def extract_node(state: PipelineState) -> dict:
    data = dict(state["data"])
    data["attributes"] = extract_attributes(data)
    return {"data": data}


def taxonomy_node(state: PipelineState) -> dict:
    data = dict(state["data"])

    data["category"] = map_category(
        data["normalized_title"],
        data.get("category")
    )

    return {"data": data}


def seo_node(state: PipelineState) -> dict:
    data = dict(state["data"])

    data["seo_title"], data["seo_description"] = generate_seo(
        data["normalized_title"],
        data["category"],
        data["attributes"]
    )

    return {"data": data}


def validation_node(state: PipelineState) -> dict:
    errors = validate(state["data"])
    return {"validation_errors": errors}


def increment_retry_node(state: PipelineState) -> dict:
    return {"retries": state.get("retries", 0) + 1}


def approved_node(state: PipelineState) -> dict:
    return {
        "status": "approved",
        "reviewer_notes": ""
    }


def human_review_node(state: PipelineState) -> dict:
    """
    Pause workflow until a human reviewer submits a decision.

    LangGraph saves the state before interrupting.
    On resume, this node receives the review decision.
    """

    review_payload = {
        "type": "product_review",
        "product": state["data"],
        "validation_errors": state.get("validation_errors", []),
        "message": "This product requires human approval."
    }

    decision = interrupt(review_payload)

    return {
        "status": (
            "approved" if decision["approved"] else "rejected"
        ),
        "reviewer_notes": decision.get("reviewer_notes", "")
    }


# --------------------------------------------------
# 4. Conditional routing
# --------------------------------------------------

SEO_ERRORS = {
    "SEO title is missing",
    "SEO title exceeds 70 characters",
    "SEO description exceeds 300 characters"
}


def route_after_validation(state: PipelineState) -> str:
    errors = state.get("validation_errors", [])

    if not errors:
        return "approved"

    # Retry only SEO-related failures.
    if (
        all(error in SEO_ERRORS for error in errors)
        and state.get("retries", 0) < settings.max_retries
    ):
        return "retry_seo"

    return "human_review"


# --------------------------------------------------
# 5. Build LangGraph
# --------------------------------------------------

def build_pipeline_graph():
    workflow = StateGraph(PipelineState)

    workflow.add_node("normalize", normalize_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("taxonomy", taxonomy_node)
    workflow.add_node("seo", seo_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("increment_retry", increment_retry_node)
    workflow.add_node("approved", approved_node)
    workflow.add_node("human_review", human_review_node)

    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "extract")
    workflow.add_edge("extract", "taxonomy")
    workflow.add_edge("taxonomy", "seo")
    workflow.add_edge("seo", "validate")

    workflow.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "approved": "approved",
            "retry_seo": "increment_retry",
            "human_review": "human_review"
        }
    )

    workflow.add_edge("increment_retry", "seo")

    workflow.add_edge("approved", END)
    workflow.add_edge("human_review", END)

    return workflow.compile(checkpointer=checkpointer)


pipeline_graph = build_pipeline_graph()


# --------------------------------------------------
# 6. Format workflow response
# --------------------------------------------------

def format_result(result: dict, thread_id: str) -> dict:
    data = result.get("data", {})

    is_interrupted = bool(result.get("__interrupt__"))

    return {
        **data,
        "validation_errors": result.get("validation_errors", []),
        "retries": result.get("retries", 0),
        "status": (
            "pending_review"
            if is_interrupted
            else result.get("status", "needs_review")
        ),
        "reviewer_notes": result.get("reviewer_notes", ""),
        "workflow_thread_id": thread_id
    }


# --------------------------------------------------
# 7. Start enrichment
# --------------------------------------------------

def run_pipeline(product: ProductInput) -> dict:
    """Start a new enrichment workflow."""

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = pipeline_graph.invoke(
        {
            "product": product,
            "retries": 0
        },
        config=config
    )

    return format_result(result, thread_id)


# --------------------------------------------------
# 8. Resume after human review
# --------------------------------------------------

def resume_pipeline(
    thread_id: str,
    approved: bool,
    reviewer_notes: str = ""
) -> dict:
    """Resume a paused workflow with a human review decision."""

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = pipeline_graph.invoke(
        Command(
            resume={
                "approved": approved,
                "reviewer_notes": reviewer_notes
            }
        ),
        config=config
    )

    return format_result(result, thread_id)
