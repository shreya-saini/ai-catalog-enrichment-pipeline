
"""Product attribute extraction adapter."""

from app.services.llm import extract_product_attributes


def extract_attributes(data: dict) -> dict:
    return extract_product_attributes(
        title=data.get("normalized_title", ""),
        description=data.get("description", ""),
        existing_attributes=data.get("attributes", {})
    )
