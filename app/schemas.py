from pydantic import BaseModel, Field
from typing import Any

class ProductInput(BaseModel):
    sku: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    brand: str | None = None
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

class EnrichedProduct(BaseModel):
    sku: str
    normalized_title: str
    brand: str | None = None
    category: str
    attributes: dict[str, Any]
    seo_title: str
    seo_description: str
    status: str = "approved"
    validation_errors: list[str] = Field(default_factory=list)
    retries: int = 0

class ReviewDecision(BaseModel):
    approved: bool
    reviewer_notes: str = ""
