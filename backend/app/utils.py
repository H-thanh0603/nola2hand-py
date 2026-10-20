"""Helper dùng chung — port dần từ src/utils.js khi tới route cần."""
from datetime import datetime, timezone


def now() -> datetime:
    """UTC dạng naive, khớp kiểu timestamp của Prisma.

    Lưu ý: cột `updatedAt` của Prisma là @updatedAt — không có default trong DB,
    nên mọi insert/update đều phải tự đặt giá trị này (kể cả updateMany).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
