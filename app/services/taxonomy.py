
"""Semantic taxonomy retrieval using Gemini embeddings and SQLite."""

import json
import math
import sqlite3
from pathlib import Path

from google import genai
from google.genai import types

from app.core.config import settings


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "taxonomy_vectors.db"

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768

# Minimum cosine similarity required to accept a category.
MIN_SIMILARITY = 0.35
MIN_SIMILARITY_MARGIN = 0.04

TAXONOMY_DOCUMENTS = [
    {
        "id": "apparel",
        "category": "Apparel",
        "description": "Clothing and fashion products including shirts, t-shirts, dresses, jeans, jackets, trousers and accessories."
    },
    {
        "id": "electronics",
        "category": "Electronics",
        "description": "Electronic devices including smartphones, laptops, headphones, cameras, chargers and computers."
    },
    {
        "id": "home",
        "category": "Home",
        "description": "Home and kitchen products including furniture, sofas, chairs, lamps, bedding, kitchenware and home decor."
    },
    {
        "id": "beauty",
        "category": "Beauty",
        "description": "Beauty and personal care products including shampoo, skincare, serums, moisturizers, lipstick and cleansers."
    },
    {
        "id": "pet_supplies",
        "category": "Pet Supplies",
        "description": "Products for pets including dog food, cat food, animal nutrition, pet toys, leashes, collars and grooming products."
    }
]



_gemini_client = None


def get_client():
    global _gemini_client

    if _gemini_client is None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is missing.")

        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key
        )

    return _gemini_client


def generate_embeddings(texts: list[str], task_type: str) -> list[list[float]]:
    """Generate text embeddings using Gemini."""

    response = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS
        )
    )

    if not response.embeddings:
        raise RuntimeError("Gemini returned no embeddings.")

    return [item.values for item in response.embeddings]


def initialize_taxonomy():
    """Persist taxonomy documents and their embeddings in SQLite."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS taxonomy_vectors (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
        """)

        count = connection.execute(
            "SELECT COUNT(*) FROM taxonomy_vectors"
        ).fetchone()[0]

        if count == 0:
            documents = [item["description"] for item in TAXONOMY_DOCUMENTS]

            embeddings = generate_embeddings(
                documents,
                task_type="RETRIEVAL_DOCUMENT"
            )

            records = [
                (
                    item["id"],
                    item["category"],
                    item["description"],
                    json.dumps(embedding)
                )
                for item, embedding in zip(TAXONOMY_DOCUMENTS, embeddings)
            ]

            connection.executemany("""
                INSERT INTO taxonomy_vectors
                (id, category, description, embedding)
                VALUES (?, ?, ?, ?)
            """, records)


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Calculate cosine similarity without native vector libraries."""

    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))

    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)

def map_category(title: str, supplied: str | None = None) -> str:
    """Find the closest taxonomy category using semantic similarity."""

    query = f"{title} {supplied or ''}".strip()

    if not query:
        return supplied.strip().title() if supplied else "Uncategorized"

    initialize_taxonomy()

    query_embedding = generate_embeddings(
        [query],
        task_type="RETRIEVAL_QUERY"
    )[0]

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT category, embedding
            FROM taxonomy_vectors
        """).fetchall()

    if not rows:
        return supplied.strip().title() if supplied else "Uncategorized"

    candidates = [
        (
            category,
            cosine_similarity(query_embedding, json.loads(embedding))
        )
        for category, embedding in rows
    ]

    # Sort categories by similarity score (highest first).
    candidates.sort(key=lambda item: item[1], reverse=True)

    best_category, best_score = candidates[0]

    # Compare the best category with the second-best category.
    second_score = candidates[1][1] if len(candidates) > 1 else 0.0
    confidence_margin = best_score - second_score

    # Reject weak or ambiguous classifications.
    if (
        best_score < MIN_SIMILARITY
        or confidence_margin < MIN_SIMILARITY_MARGIN
    ):
        return supplied.strip().title() if supplied else "Uncategorized"

    return best_category