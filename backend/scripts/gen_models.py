"""Sinh app/models.py từ schema PostgreSQL đang có.

Nguồn sự thật là database thật (bảng/cột do Prisma tạo), không phải chép tay
từ schema.prisma. Chạy lại khi DB đổi:  python scripts/gen_models.py

shortcut: model chỉ có cột, chưa có relationship(); thêm dần khi route cần join.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect  # noqa: E402

from app.db import engine  # noqa: E402

SKIP_TABLES = {"_prisma_migrations", "alembic_version"}


def to_expr(col):
    """Kiểu cột trong DB -> biểu thức SQLAlchemy."""
    t = str(col["type"])
    name = t.split("(")[0].upper()

    if name in ("VARCHAR", "CHARACTER VARYING"):
        m = re.search(r"\((\d+)\)", t)
        return f"String({m.group(1)})" if m else "String"
    if name in ("TEXT", "CHARACTER"):
        return "Text"
    if name in ("INTEGER", "INT"):
        return "Integer"
    if name == "BIGINT":
        return "BigInteger"
    if name == "SMALLINT":
        return "SmallInteger"
    if name == "BOOLEAN":
        return "Boolean"
    if name.startswith("TIMESTAMP"):
        return "DateTime(timezone=True)" if "TIME ZONE" in t.upper() else "DateTime"
    if name == "DATE":
        return "Date"
    if name == "NUMERIC":
        m = re.search(r"\((\d+),\s*(\d+)\)", t)
        return f"Numeric({m.group(1)}, {m.group(2)})" if m else "Numeric"
    if name in ("DOUBLE PRECISION", "REAL"):
        return "Float"
    if name == "UUID":
        return "Uuid"
    if name in ("JSONB", "JSON"):
        return name
    if name == "BYTEA":
        return "LargeBinary"
    if name.startswith("ENUM"):
        return f'Enum(name="{col["type"].name}")'
    raise SystemExit(f"Kiểu chưa hỗ trợ: {t} (cột {col['name']})")


def main():
    insp = inspect(engine)
    tables = [t for t in insp.get_table_names(schema="public") if t not in SKIP_TABLES]
    if len(tables) != 36:
        print(f"!! mong đợi 36 bảng, thấy {len(tables)}", file=sys.stderr)

    out: list[str] = []

    for table in tables:
        pk = insp.get_pk_constraint(table, schema="public")["constrained_columns"]
        out.append(f"class {table}(Base):")
        out.append(f'    __tablename__ = "{table}"')
        out.append("")
        for col in insp.get_columns(table, schema="public"):
            args = [to_expr(col), f'name="{col["name"]}"']
            if col["name"] in pk:
                args.append("primary_key=True")
            if not col["nullable"]:
                args.append("nullable=False")
            out.append(f"    {col['name']}: Mapped[Any] = mapped_column({', '.join(args)})")
        out.append("")
        out.append("")

    body = "\n".join(out)
    generic = ["BigInteger", "Boolean", "Date", "DateTime", "Enum", "Float", "Integer", "Numeric", "String", "Text", "Uuid"]
    used = [n for n in generic if re.search(rf"\b{n}\b", body)]
    if not used:
        raise SystemExit("Không nhận ra kiểu nào — kiểm tra lại output")
    header = [
        '"""Model SQLAlchemy — sinh tự động, đừng sửa tay.',
        "",
        "Sinh lại: python scripts/gen_models.py",
        "Nguồn: database PostgreSQL của bản Node (xem PLAN.md).",
        '"""',
        "from typing import Any",
        "",
        "from sqlalchemy import " + ", ".join(used),
    ]
    if re.search(r"\bJSONB\b", body):
        header.append("from sqlalchemy.dialects.postgresql import JSONB")
    header += ["from sqlalchemy.orm import Mapped, mapped_column", "", "from .db import Base", "", "", body, ""]

    Path("app/models.py").write_text("\n".join(header))
    print(f"Đã sinh app/models.py với {len(tables)} model")


if __name__ == "__main__":
    main()
