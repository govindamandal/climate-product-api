from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import engine


def run_migrations() -> None:
    config = Config("alembic.ini")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if tables and "alembic_version" not in tables:
        command.stamp(config, "head")
        return
    command.upgrade(config, "head")
