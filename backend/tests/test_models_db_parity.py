"""Chặn lệch giữa model sinh tự động và database thật.

Chạy: pytest tests/  (cần DATABASE_URL trong .env)
"""
from sqlalchemy import inspect

from app.db import engine
from app.models import Base

SKIP = {"_prisma_migrations", "alembic_version"}


def test_moi_bang_deu_co_model():
    in_db = {t for t in inspect(engine).get_table_names(schema="public") if t not in SKIP}
    in_models = set(Base.metadata.tables)
    assert in_db == in_models, f"lệch bảng: {in_db ^ in_models}"


def test_moi_cot_khop_ten_va_thu_tu():
    insp = inspect(engine)
    for table in Base.metadata.tables.values():
        db_cols = [c["name"] for c in insp.get_columns(table.name, schema="public")]
        model_cols = [c.name for c in table.columns]
        assert db_cols == model_cols, f"{table.name}: {db_cols} != {model_cols}"


def test_khoa_chinh_khop():
    insp = inspect(engine)
    for table in Base.metadata.tables.values():
        db_pk = set(insp.get_pk_constraint(table.name, schema="public")["constrained_columns"])
        model_pk = {c.name for c in table.primary_key.columns}
        assert db_pk == model_pk, f"{table.name}: {db_pk} != {model_pk}"
