
"""LLM operations for product catalog enrichment."""

import json
from google import genai

from app.core.config import settings


def _get_gemini_client():
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    return genai.Client(api_key=settings.gemini_api_key)


def extract_product_attributes(
    title: str,
    description: str,
    existing_attributes: dict
) -> dict:
    """Extract product attributes without inventing specifications."""

    existing_attributes = existing_attributes or {}

    if settings.llm_mode == "mock":
        attrs = dict(existing_attributes)
        text = f"{title} {description}".lower()

        for size in ("xs", "s", "m", "l", "xl", "xxl"):
            if f" size {size}" in f" {text}" or f"({size})" in text:
                attrs.setdefault("size", size.upper())
                break

        for color in (
            "black", "white", "blue", "red",
            "green", "pink", "brown"
        ):
            if color in text:
                attrs.setdefault("color", color)
                break

        return attrs

    if settings.llm_mode != "gemini":
        raise ValueError(f"Unsupported LLM mode: {settings.llm_mode}")

    prompt = f"""
You are an expert e-commerce product data extraction system.

Extract product attributes from the supplied product information.

Product title: {title}
Product description: {description}

Existing supplier attributes:
{json.dumps(existing_attributes)}

Rules:
1. Extract only facts explicitly supported by the title or description.
2. Do not invent or guess missing values.
3. Identify relevant attributes such as brand, color, size, weight,
   material, pet_type, breed, life_stage, gender and model where applicable.
4. Preserve useful supplier attributes.
5. Use concise, consistent values.
6. Return a valid JSON object containing attributes only.
7. Do not include explanations or Markdown.

Example:
{{
    "color": "Black",
    "material": "Cotton",
    "size": "Large"
}}
"""

    client = _get_gemini_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )

    extracted = json.loads(response.text)

    if not isinstance(extracted, dict):
        raise ValueError("Gemini returned invalid attribute data.")

    # Supplier-provided attributes take precedence.
    extracted.update(existing_attributes)

    return extracted


def generate_seo(
    title: str,
    category: str,
    attributes: dict
) -> tuple[str, str]:

    if settings.llm_mode == "mock":
        seo_title = f"{title.strip()} | {category}"
        detail = ", ".join(
            f"{key}: {value}"
            for key, value in list(attributes.items())[:4]
        )
        seo_description = (
            f"Explore {title.strip()}, a {category.lower()} option. {detail}"
        )
        return seo_title[:70], seo_description[:300]

    if settings.llm_mode != "gemini":
        raise ValueError(f"Unsupported LLM mode: {settings.llm_mode}")

    prompt = f"""
You are an expert e-commerce SEO copywriter.

Product title: {title}
Category: {category}
Verified attributes: {json.dumps(attributes)}

Requirements:
1. SEO title must be under 70 characters.
2. SEO description must be under 300 characters.
3. Use natural, readable language.
4. Include relevant product keywords.
5. Never invent product features or specifications.
6. Return valid JSON with exactly these keys:
   seo_title
   seo_description
"""

    client = _get_gemini_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )

    result = json.loads(response.text)

    return (
        result["seo_title"].strip()[:70],
        result["seo_description"].strip()[:300]
    )
