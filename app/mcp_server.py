
"""MCP tools for the AI Catalog Enrichment Pipeline."""

from typing import Any

from fastmcp import FastMCP

from app.db.database import init_db

from app.schemas import ProductInput
from app.services.taxonomy import map_category, TAXONOMY_DOCUMENTS
from app.services.validator import validate
from app.db.repository import (
    save_product,
    get_product as db_get_product,
    list_products as db_list_products,
    list_products_by_status,
)
from app.workflows.pipeline import run_pipeline, resume_pipeline


mcp = FastMCP("AI Catalog Enrichment Pipeline")
init_db()

# --------------------------------------------------
# 1. Enrich one product
# --------------------------------------------------

@mcp.tool()
def enrich_product(
    sku: str,
    title: str,
    description: str = "",
    brand: str | None = None,
    category: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict:
    """Run the complete AI enrichment workflow for one product."""

    product = ProductInput(
        sku=sku,
        title=title,
        description=description,
        brand=brand,
        category=category,
        attributes=attributes or {},
    )

    result = run_pipeline(product)

    save_product(
        product.sku,
        product.model_dump(),
        result
    )

    return result


# --------------------------------------------------
# 2. Batch enrichment
# --------------------------------------------------

@mcp.tool()
def enrich_products_batch(products: list[dict]) -> dict:
    """Enrich multiple products. Maximum batch size is 100."""

    if not products:
        raise ValueError("At least one product is required.")

    if len(products) > 100:
        raise ValueError("Maximum batch size is 100.")

    results = []

    for item in products:
        product = ProductInput(**item)

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
# 3. Retrieve one product
# --------------------------------------------------

@mcp.tool()
def get_product(sku: str) -> dict:
    """Retrieve a product, including its original input and enrichment."""

    item = db_get_product(sku)

    if not item:
        raise ValueError(f"Product with SKU {sku} was not found.")

    return item


# --------------------------------------------------
# 4. List products
# --------------------------------------------------

@mcp.tool()
def list_products() -> list[dict]:
    """List product SKUs, statuses and creation dates."""

    return db_list_products()


# --------------------------------------------------
# 5. Human review queue
# --------------------------------------------------

@mcp.tool()
def get_review_queue() -> list[dict]:
    """Retrieve all products waiting for human review."""

    return list_products_by_status("pending_review")


# --------------------------------------------------
# 6. Approve or reject a product
# --------------------------------------------------

@mcp.tool()
def review_product(
    sku: str,
    approved: bool,
    reviewer_notes: str = "",
) -> dict:
    """Approve or reject a pending product and resume its LangGraph workflow."""

    item = db_get_product(sku)

    if not item:
        raise ValueError(f"Product with SKU {sku} was not found.")

    output = item.get("output") or {}

    if output.get("status") != "pending_review":
        raise ValueError("This product is not waiting for human review.")

    thread_id = output.get("workflow_thread_id")

    if not thread_id:
        raise ValueError("No LangGraph workflow thread ID was found.")

    result = resume_pipeline(
        thread_id=thread_id,
        approved=approved,
        reviewer_notes=reviewer_notes,
    )

    save_product(sku, item["input"], result)

    return result


# --------------------------------------------------
# 7. Retrieve taxonomy
# --------------------------------------------------

@mcp.tool()
def get_taxonomy() -> list[dict]:
    """Return the available product categories and descriptions."""

    return TAXONOMY_DOCUMENTS


# --------------------------------------------------
# 8. Existing classification tool
# --------------------------------------------------

@mcp.tool()
def classify_product(
    title: str,
    supplied_category: str | None = None,
) -> str:
    """Classify a product using semantic taxonomy retrieval."""

    return map_category(title, supplied_category)


# --------------------------------------------------
# 9. Existing validation tool
# --------------------------------------------------

@mcp.tool()
def validate_product(record: dict) -> list[str]:
    """Validate an enriched product record and return its issues."""

    return validate(record)


if __name__ == "__main__":
    mcp.run()
