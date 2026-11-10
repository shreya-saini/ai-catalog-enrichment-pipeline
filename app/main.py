
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.schemas import ProductInput, ReviewDecision
from app.db.database import init_db
from app.db.repository import save_product, get_product, list_products
from app.workflows.pipeline import run_pipeline, resume_pipeline


# --------------------------------------------------
# Application lifecycle
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Catalog Enrichment Pipeline",
    version="0.2.0",
    description=(
        "AI-powered catalog enrichment using Gemini, "
        "LangGraph, semantic taxonomy and human review."
    ),
    lifespan=lifespan,
)


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------
# Product enrichment
# --------------------------------------------------

@app.post("/api/v1/enrich")
def enrich(product: ProductInput):
    result = run_pipeline(product)

    save_product(
        product.sku,
        product.model_dump(),
        result
    )

    return result


# --------------------------------------------------
# Batch enrichment
# --------------------------------------------------

@app.post("/api/v1/enrich/batch")
def enrich_batch(products: list[ProductInput]):
    if len(products) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum batch size is 100"
        )

    results = []

    for product in products:
        result = run_pipeline(product)

        save_product(
            product.sku,
            product.model_dump(),
            result
        )

        results.append(result)

    return {
        "count": len(results),
        "items": results
    }


# --------------------------------------------------
# Product retrieval
# --------------------------------------------------

@app.get("/api/v1/products")
def products():
    return list_products()


@app.get("/api/v1/products/{sku}")
def product(sku: str):
    item = get_product(sku)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return item


# --------------------------------------------------
# Human review
# --------------------------------------------------

@app.post("/api/v1/products/{sku}/review")
def review(sku: str, decision: ReviewDecision):
    item = get_product(sku)

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    output = item.get("output") or {}

    if output.get("status") != "pending_review":
        raise HTTPException(
            status_code=409,
            detail="Product is not awaiting human review"
        )

    thread_id = output.get("workflow_thread_id")

    if not thread_id:
        raise HTTPException(
            status_code=400,
            detail="Workflow thread ID is missing"
        )

    try:
        result = resume_pipeline(
            thread_id=thread_id,
            approved=decision.approved,
            reviewer_notes=decision.reviewer_notes
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to resume review workflow: {str(exc)}"
        )

    save_product(
        sku,
        item["input"],
        result
    )

    return result
