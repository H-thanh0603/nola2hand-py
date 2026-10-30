"""Model cho tính năng tạo video quảng bá — tách khỏi `models.py` (file sinh tự động).

`models.py` được sinh lại từ schema PostgreSQL bằng `scripts/gen_models.py`; đặt model
mới ở đây rồi import vào cuối `models.py` để không bị ghi đè khi chạy lại script.
"""
from typing import Any

from sqlalchemy import Enum, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .types import JsDateTime

VideoJobStatus = Enum(
    "QUEUED", "RUNNING", "DONE", "FAILED", "CANCELLED", name="VideoJobStatus"
)

class VideoJob(Base):
    __tablename__ = "VideoJob"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False, autoincrement=True)
    sellerId: Mapped[Any] = mapped_column(Integer, name="sellerId", nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId")
    agentJobId: Mapped[Any] = mapped_column(Text, name="agentJobId")
    prompt: Mapped[Any] = mapped_column(Text, name="prompt", nullable=False)
    finalPrompt: Mapped[Any] = mapped_column(Text, name="finalPrompt", nullable=False)
    status: Mapped[Any] = mapped_column(
        VideoJobStatus, name="status", nullable=False, server_default=text("'QUEUED'::\"VideoJobStatus\"")
    )
    error: Mapped[Any] = mapped_column(Text, name="error")
    videoUrl: Mapped[Any] = mapped_column(Text, name="videoUrl")
    createdAt: Mapped[Any] = mapped_column(
        JsDateTime, name="createdAt", nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    finishedAt: Mapped[Any] = mapped_column(JsDateTime, name="finishedAt")
