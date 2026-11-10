def validate(data: dict) -> list[str]:
    errors=[]
    if not data.get("sku"): errors.append("SKU is required")
    if len(data.get("normalized_title", "")) < 3: errors.append("Title must contain at least 3 characters")
    if not data.get("category") or data["category"] == "Uncategorized": errors.append("Category needs human confirmation")
    if not data.get("seo_title"): errors.append("SEO title is missing")
    if len(data.get("seo_title", "")) > 70: errors.append("SEO title exceeds 70 characters")
    if len(data.get("seo_description", "")) > 300: errors.append("SEO description exceeds 300 characters")
    return errors
