import json
from sqlalchemy import text
from app.db.database import engine

def save_product(sku: str, input_data: dict, output_data: dict):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO products(sku,input_json,output_json,status)
        VALUES(:sku,:input,:output,:status)
        ON CONFLICT(sku) DO UPDATE SET input_json=excluded.input_json,
        output_json=excluded.output_json,status=excluded.status"""),
        {"sku":sku,"input":json.dumps(input_data),"output":json.dumps(output_data),"status":output_data["status"]})

def get_product(sku: str):
    with engine.begin() as conn:
        row=conn.execute(text("SELECT * FROM products WHERE sku=:sku"), {"sku":sku}).mappings().first()
    if not row: return None
    return {"sku":row["sku"],"input":json.loads(row["input_json"]),
            "output":json.loads(row["output_json"]) if row["output_json"] else None,
            "status":row["status"],"created_at":str(row["created_at"])}

def list_products():
    with engine.begin() as conn:
        rows=conn.execute(text("SELECT sku,status,created_at FROM products ORDER BY created_at DESC")).mappings().all()
    return [dict(r) for r in rows]



def list_products_by_status(status: str):
    """Return complete product records filtered by workflow status."""
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT sku, input_json, output_json, status, created_at
                FROM products
                WHERE status = :status
                ORDER BY created_at DESC
            """),
            {"status": status}
        ).mappings().all()

    return [
        {
            "sku": row["sku"],
            "input": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]) if row["output_json"] else None,
            "status": row["status"],
            "created_at": str(row["created_at"])
        }
        for row in rows
    ]
