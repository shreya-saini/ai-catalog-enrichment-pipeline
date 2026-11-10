import re
from app.schemas import ProductInput

def normalize(product: ProductInput) -> dict:
    title = re.sub(r"\s+", " ", product.title).strip()
    return {"sku": product.sku.strip(), "normalized_title": title,
            "brand": product.brand.strip() if product.brand else None,
            "category": (product.category or "Uncategorized").strip().title(),
            "attributes": {str(k).strip().lower().replace(" ", "_"): v for k,v in product.attributes.items()},
            "description": product.description.strip()}
