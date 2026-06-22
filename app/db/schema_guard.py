from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if "products" not in inspector.get_table_names():
        return
    product_columns = {column["name"] for column in inspector.get_columns("products")}
    missing_columns = [
        ("image_url", "VARCHAR(600)"),
        ("image_key", "VARCHAR(500)"),
    ]
    with engine.begin() as connection:
        for name, column_type in missing_columns:
            if name not in product_columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {name} {column_type}"))
