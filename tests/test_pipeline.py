
from app.schemas import ProductInput
import app.workflows.pipeline as pipeline
import app.services.extractor as extractor


def mock_extract(title, description, existing_attributes):
    extracted = {}

    if "t-shirt" in title.lower():
        extracted["material"] = "cotton"

    return extracted


def mock_seo(title, category, attributes):
    return (
        f"{title} | Shop Online",
        f"Explore {title} in our online store."
    )


def mock_category(title, supplied=None):
    title_lower = title.lower()

    if "mystery widget" in title_lower:
        return "Uncategorized"

    if supplied and supplied.lower() != "uncategorized":
        return supplied.strip().title()

    if any(word in title_lower for word in ["t-shirt", "shirt", "dress"]):
        return "Apparel"

    return "Uncategorized"


def setup_module():
    pipeline.map_category = mock_category
    pipeline.generate_seo = mock_seo
    extractor.extract_product_attributes = mock_extract


def test_pipeline_enriches_apparel():
    result = pipeline.run_pipeline(
        ProductInput(
            sku="TS-1",
            title="  Blue cotton t-shirt  ",
            attributes={"material": "cotton"}
        )
    )

    assert result["normalized_title"] == "Blue cotton t-shirt"
    assert result["category"] == "Apparel"
    assert result["seo_title"]
    assert result["seo_description"]
    assert result["status"] == "approved"
    assert result["validation_errors"] == []


def test_unknown_category_needs_review():
    result = pipeline.run_pipeline(
        ProductInput(
            sku="X-1",
            title="Mystery widget"
        )
    )

    assert result["category"] == "Uncategorized"
    assert result["status"] == "pending_review"
    assert "Category needs human confirmation" in result["validation_errors"]
