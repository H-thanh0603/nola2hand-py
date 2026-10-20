"""Chặn lệch giữa model sinh tự động và database thật.

Chạy: pytest tests/  (cần DATABASE_URL trong .env)
"""
from sqlalchemy import Enum, inspect, text

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


def _db_types():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name, column_name, data_type, udt_name
                FROM information_schema.columns WHERE table_schema = 'public'
                """
            )
        )
        return {(r.table_name, r.column_name): (r.data_type, r.udt_name) for r in rows}


def test_cot_enum_duoc_map_thanh_enum():
    """Enum map thành String sẽ chỉ lỗi khi chạy truy vấn — chặn ngay ở đây."""
    types = _db_types()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            data_type, udt_name = types[(table.name, column.name)]
            is_db_enum = data_type == "USER-DEFINED"
            if is_db_enum:
                assert isinstance(column.type, Enum), f"{table.name}.{column.name} phải là Enum"
                assert column.type.name == udt_name, f"{table.name}.{column.name}: tên enum lệch"
                assert set(column.type.enums) == _enum_labels(udt_name), f"{table.name}.{column.name}: thiếu giá trị"
            else:
                assert not isinstance(column.type, Enum), f"{table.name}.{column.name} không phải enum trong DB"


def _enum_labels(udt_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = :name
                """
            ),
            {"name": udt_name},
        )
        return {r.enumlabel for r in rows}


def test_cot_co_default_trong_db_deu_khai_server_default():
    """Thiếu server_default, SQLAlchemy chèn NULL thay vì để DB dùng default.

    Prisma dựa vào default của DB (isVerified, status, sessionVersion...) nên lệch
    chỗ này làm đăng ký tài khoản chết với NotNullViolation.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT table_name, column_name, column_default
                FROM information_schema.columns WHERE table_schema = 'public'
                """
            )
        )
        db_defaults = {
            (r.table_name, r.column_name): r.column_default
            for r in rows
            if r.column_default and "nextval" not in r.column_default and r.table_name not in SKIP
        }

    model_defaults = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.server_default is not None
    }
    assert model_defaults == set(db_defaults), f"lệch default: {model_defaults ^ set(db_defaults)}"
