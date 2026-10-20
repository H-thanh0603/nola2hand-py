"""Sinh app/models.py từ schema PostgreSQL đang có.

Nguồn sự thật là database thật (bảng/cột do Prisma tạo), không phải chép tay
từ schema.prisma. Chạy lại khi DB đổi:  python scripts/gen_models.py

Kiểu cột đọc từ information_schema, không dùng SQLAlchemy inspector: inspector
trả cột enum PostgreSQL về dạng VARCHAR(n), khiến `status == 'ACTIVE'` lỗi
"operator does not exist".

shortcut: model chỉ có cột, chưa có relationship(); thêm dần khi route cần join.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402

SKIP_TABLES = {"_prisma_migrations", "alembic_version"}

COLUMNS_SQL = text(
    """
    SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default,
           character_maximum_length, numeric_precision, numeric_scale
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position
    """
)
PRIMARY_KEYS_SQL = text(
    """
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
    """
)
ENUM_VALUES_SQL = text(
    """
    SELECT t.typname, e.enumlabel
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    ORDER BY t.typname, e.enumsortorder
    """
)

IMPORT_CANDIDATES = [
    "BigInteger",
    "Boolean",
    "Date",
    "Enum",
    "Float",
    "Integer",
    "Numeric",
    "String",
    "Text",
    "Uuid",
]

SIMPLE_TYPES = {
    "boolean": "Boolean",
    "integer": "Integer",
    "bigint": "BigInteger",
    "smallint": "SmallInteger",
    "text": "Text",
    "date": "Date",
    "uuid": "Uuid",
    "jsonb": "JSONB",
    "json": "JSON",
    "bytea": "LargeBinary",
}


def to_expr(col: dict, enums: dict[str, list[str]]) -> str:
    data_type = col["data_type"]
    if data_type in SIMPLE_TYPES:
        return SIMPLE_TYPES[data_type]
    if data_type == "character varying":
        length = col["character_maximum_length"]
        return f"String({length})" if length else "String"
    if data_type == "timestamp with time zone":
        return "JsDateTime(timezone=True)"
    if data_type == "timestamp without time zone":
        return "JsDateTime"
    if data_type == "numeric":
        return f"Numeric({col['numeric_precision']}, {col['numeric_scale']})"
    if data_type in ("double precision", "real"):
        return "Float"
    if data_type == "USER-DEFINED":
        # enum PostgreSQL. Phải kèm danh sách giá trị, nếu không SQLAlchemy
        # không đọc nổi giá trị khi SELECT (LookupError).
        name = col["udt_name"]
        labels = ", ".join(f'"{label}"' for label in enums[name])
        return f"Enum({labels}, name=\"{name}\")"
    raise SystemExit(f"Kiểu chưa hỗ trợ: {data_type} (cột {col['table_name']}.{col['column_name']})")


def main():
    with engine.connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(COLUMNS_SQL)]
        pks: dict[str, set[str]] = {}
        for row in conn.execute(PRIMARY_KEYS_SQL):
            pks.setdefault(row.table_name, set()).add(row.column_name)
        enums: dict[str, list[str]] = {}
        for row in conn.execute(ENUM_VALUES_SQL):
            enums.setdefault(row.typname, []).append(row.enumlabel)

    tables: dict[str, list[dict]] = {}
    for row in rows:
        if row["table_name"] not in SKIP_TABLES:
            tables.setdefault(row["table_name"], []).append(row)

    if len(tables) != 36:
        print(f"!! mong đợi 36 bảng, thấy {len(tables)}", file=sys.stderr)

    out: list[str] = []
    for table, cols in tables.items():
        out.append(f"class {table}(Base):")
        out.append(f'    __tablename__ = "{table}"')
        out.append("")
        for col in cols:
            args = [to_expr(col, enums), f'name="{col["column_name"]}"']
            if col["column_name"] in pks.get(table, set()):
                args.append("primary_key=True")
            if col["is_nullable"] == "NO":
                args.append("nullable=False")
            default = col["column_default"]
            # serial (nextval) để DB tự sinh, không cần khai báo. Còn lại phải khai
            # báo server_default, nếu không SQLAlchemy chèn NULL và vi phạm NOT NULL
            # thay vì để DB dùng default (Prisma dựa vào default này).
            if default and "nextval" not in default:
                args.append(f"server_default=text({default!r})")
            out.append(f"    {col['column_name']}: Mapped[Any] = mapped_column({', '.join(args)})")
        out.append("")
        out.append("")

    body = "\n".join(out)
    imported = [name for name in IMPORT_CANDIDATES if re.search(rf"\b{name}\b", body)]
    if "text(" in body:
        imported.append("text")
    header = [
        '"""Model SQLAlchemy — sinh tự động, đừng sửa tay.',
        "",
        "Sinh lại: python scripts/gen_models.py",
        "Nguồn: database PostgreSQL của bản Node (xem PLAN.md).",
        '"""',
        "from typing import Any",
        "",
        "from sqlalchemy import " + ", ".join(imported),
    ]
    if re.search(r"\bJSONB\b", body):
        header.append("from sqlalchemy.dialects.postgresql import JSONB")
    header.append("from sqlalchemy.orm import Mapped, mapped_column")
    header.append("")
    header.append("from .db import Base")
    if re.search(r"\bJsDateTime\b", body):
        header.append("from .types import JsDateTime")
    header += ["", "", body, ""]

    Path("app/models.py").write_text("\n".join(header))
    print(f"Đã sinh app/models.py với {len(tables)} model")


if __name__ == "__main__":
    main()
