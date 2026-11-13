"""thêm bảng VideoJob cho tính năng tạo video quảng bá

Revision ID: a1f2c3d4e5b6
Revises: 7c0952c8735d
Create Date: 2026-10-30

Chỉ THÊM bảng + enum + index; không đổi/xoá cột cũ (DB dùng chung với bản Node).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f2c3d4e5b6"
down_revision: Union[str, Sequence[str], None] = "7c0952c8735d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS = sa.Enum(
    "QUEUED", "RUNNING", "DONE", "FAILED", "CANCELLED", name="VideoJobStatus"
)

def upgrade() -> None:
    # Enum được tạo kèm create_table; gọi STATUS.create() trước sẽ bị tạo hai lần.
    op.create_table(
        "VideoJob",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sellerId", sa.Integer(), nullable=False),
        sa.Column("listingId", sa.Integer(), nullable=True),
        sa.Column("agentJobId", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("finalPrompt", sa.Text(), nullable=False),
        sa.Column("status", STATUS, server_default=sa.text("'QUEUED'::\"VideoJobStatus\""), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("videoUrl", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finishedAt", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("VideoJob_sellerId_idx", "VideoJob", ["sellerId"])
    op.create_index("VideoJob_listingId_idx", "VideoJob", ["listingId"])

def downgrade() -> None:
    op.drop_index("VideoJob_listingId_idx", table_name="VideoJob")
    op.drop_index("VideoJob_sellerId_idx", table_name="VideoJob")
    op.drop_table("VideoJob")
    STATUS.drop(op.get_bind(), checkfirst=True)
