"""Auth: đăng ký / đăng nhập / quên mật khẩu — port src/routes/auth.js."""
import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..limits import MemoryLimiter, mail_limit
from ..models import Role, SellerProfile, User, UserRole, Wallet
from ..security import create_access_token, hash_password, verify_password
from ..serialize import to_dict
from ..services.mail import email_mode, send_account_email
from ..utils import now
from ..validators import clean_email, password, phone_vn

# Bản Node đặt rateLimit 100 lượt / 15 phút cho cả nhóm /api/v1/auth (src/app.js:38).
auth_limiter = MemoryLimiter(100, 15 * 60 * 1000)


def auth_rate_limit(request: Request) -> None:
    auth_limiter.check(request.client.host if request.client else "unknown")


router = APIRouter(dependencies=[Depends(auth_rate_limit)])

OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
VERIFY_TOKEN_TTL = timedelta(days=1)
RESET_TOKEN_TTL = timedelta(minutes=15)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _make_otp() -> tuple[str, str, "object"]:
    otp = str(secrets.randbelow(900000) + 100000)  # crypto.randomInt(100000, 1000000)
    return otp, _sha256(otp), now() + OTP_TTL


def _otp_columns(kind: str) -> tuple[str, str, str]:
    return (
        ("emailOtpHash", "emailOtpExpiresAt", "emailOtpAttempts")
        if kind == "verify"
        else ("passwordOtpHash", "passwordOtpExpiresAt", "passwordOtpAttempts")
    )


def consume_otp(db: Session, kind: str, email: str, otp: str) -> tuple[dict, User | None]:
    """Trả ({'ok': True}, user) hoặc ({'error': ...}, None) — giống consumeOtp bên Node."""
    hash_col, exp_col, att_col = _otp_columns(kind)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    stored_hash = getattr(user, hash_col) if user else None
    if user is None or not stored_hash:
        return {"error": "Mã OTP chưa được gửi, hãy bấm Gửi lại"}, None

    attempts, expires_at = getattr(user, att_col), getattr(user, exp_col)
    if (attempts or 0) >= OTP_MAX_ATTEMPTS or (expires_at and expires_at <= now()):
        return {"error": "Mã OTP đã hết hạn hoặc quá số lần thử, hãy bấm Gửi lại", "expired": True}, None

    if _sha256(otp) != stored_hash:
        db.execute(
            update(User).where(User.id == user.id).values({att_col: (attempts or 0) + 1, User.updatedAt: now()})
        )
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - (attempts or 0) - 1
        return {"error": f"Mã OTP chưa đúng (còn {remaining} lượt)"}, None

    db.execute(
        update(User)
        .where(User.id == user.id)
        .values({hash_col: None, exp_col: None, att_col: 0, User.updatedAt: now()})
    )
    db.commit()
    return {"ok": True}, user


def _roles_of(db: Session, user_id: int) -> list[str]:
    return list(
        db.execute(select(Role.name).join(UserRole, UserRole.roleId == Role.id).where(UserRole.userId == user_id)).scalars()
    )


def _auth_payload(db: Session, user: User) -> dict:
    return {
        "token": create_access_token(user.id, user.sessionVersion),
        "user": {
            "id": user.id,
            "fullName": user.fullName,
            "email": user.email,
            "avatarUrl": user.avatarUrl,
            "roles": _roles_of(db, user.id),
            "canManageRoles": user.canManageRoles is True,
        },
    }


def _buyer_role_id(db: Session) -> int | None:
    return db.execute(select(Role.id).where(Role.name == "BUYER")).scalar_one_or_none()


# ---------------------------------------------------------------- kiểu dữ liệu


class RegisterIn(BaseModel):
    fullName: str
    email: str
    password: str
    phone: str | None = None

    @field_validator("fullName")
    @classmethod
    def _full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Họ tên tối thiểu 2 ký tự")
        if len(v) > 100:
            raise ValueError("Họ tên tối đa 100 ký tự")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return password(v, 6)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = phone_vn(v)
        if len(v) > 20:
            raise ValueError("String must contain at most 20 character(s)")
        return v


class LoginIn(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("String must contain at least 1 character(s)")
        return v


class GoogleIn(BaseModel):
    idToken: str

    @field_validator("idToken")
    @classmethod
    def _token(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("String must contain at least 1 character(s)")
        return v


class EmailIn(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v)


class ResetPasswordIn(BaseModel):
    resetToken: str
    newPassword: str

    @field_validator("newPassword")
    @classmethod
    def _password(cls, v: str) -> str:
        return password(v, 6, "Mật khẩu mới")


class VerifyEmailIn(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _token(cls, v: str) -> str:
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError("Invalid string: must match pattern /^[a-f0-9]{64}$/")
        return v


class OtpIn(BaseModel):
    email: str
    otp: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return clean_email(v)

    @field_validator("otp")
    @classmethod
    def _otp(cls, v: str) -> str:
        v = v.strip()
        if len(v) != 6 or not v.isdigit():
            raise ValueError("OTP gồm 6 chữ số")
        return v


class ResetPasswordOtpIn(OtpIn):
    newPassword: str

    @field_validator("newPassword")
    @classmethod
    def _password(cls, v: str) -> str:
        return password(v, 6, "Mật khẩu mới")


class ChangePasswordIn(BaseModel):
    currentPassword: str
    newPassword: str

    @field_validator("currentPassword")
    @classmethod
    def _current(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("String must contain at least 1 character(s)")
        if len(v) > 72:
            raise ValueError("String must contain at most 72 character(s)")
        return v

    @field_validator("newPassword")
    @classmethod
    def _new(cls, v: str) -> str:
        return password(v, 8, "Mật khẩu mới")


# ------------------------------------------------------------------- endpoint


@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.execute(select(User.id).where(User.email == payload.email)).scalar_one_or_none() is not None:
        raise ApiError(409, "Email đã được đăng ký")

    verification_token = secrets.token_hex(32)
    otp, otp_hash, otp_expires = _make_otp()
    moment = now()

    user = User(
        fullName=payload.fullName,
        email=payload.email,
        passwordHash=hash_password(payload.password),
        phone=payload.phone,
        emailVerificationTokenHash=_sha256(verification_token),
        emailVerificationExpiresAt=moment + VERIFY_TOKEN_TTL,
        emailOtpHash=otp_hash,
        emailOtpExpiresAt=otp_expires,
        createdAt=moment,
        updatedAt=moment,
    )
    db.add(user)
    db.flush()
    db.add(Wallet(userId=user.id))

    buyer_role_id = _buyer_role_id(db)
    if buyer_role_id is not None:
        db.add(UserRole(userId=user.id, roleId=buyer_role_id))
    db.commit()

    delivery = "FAILED"
    try:
        delivery = send_account_email(payload.email, "verify", verification_token, otp)
    except ApiError:
        pass  # Thư hỏng vẫn tạo được tài khoản, giống bản Node.

    message = {
        "EMAIL": "Đăng ký thành công, hãy kiểm tra email xác nhận",
        "LOCAL_OUTBOX": "Đăng ký thành công. Thư xác nhận được lưu trong hộp thư development trên máy chủ.",
    }.get(delivery, "Tài khoản đã tạo. Chưa gửi được thư, hãy yêu cầu gửi lại xác nhận.")

    return {
        "message": message,
        "emailDelivery": delivery,
        "token": create_access_token(user.id, user.sessionVersion),
        "user": {"id": user.id, "fullName": user.fullName, "email": user.email},
    }


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None:
        raise ApiError(401, "Email hoặc mật khẩu chưa đúng")
    if user.status == "BANNED":
        raise ApiError(403, f"Tài khoản đã bị khóa: {user.banReason or ''}")
    if not verify_password(payload.password, user.passwordHash):
        raise ApiError(401, "Email hoặc mật khẩu chưa đúng")
    return _auth_payload(db, user)


@router.post("/google")
def google_login(payload: GoogleIn, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise ApiError(500, "Server chưa cấu hình GOOGLE_CLIENT_ID")
    try:
        info = google_id_token.verify_oauth2_token(
            payload.idToken,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:  # google-auth ném nhiều loại lỗi khác nhau
        raise ApiError(401, "Google token không hợp lệ") from exc

    google_id, email = info.get("sub"), info.get("email")
    if not email or not info.get("email_verified"):
        raise ApiError(401, "Google chưa xác minh email")

    user = db.execute(
        select(User).where((User.googleId == google_id) | (User.email == email))
    ).scalars().first()
    moment = now()

    if user is not None and user.googleId and user.googleId != google_id:
        raise ApiError(401, "Email đã liên kết với tài khoản Google khác")

    if user is not None and not user.googleId:
        # Tài khoản email có sẵn → liên kết Google.
        user.googleId = google_id
        user.isVerified = True
        user.emailVerifiedAt = moment
        user.avatarUrl = user.avatarUrl or info.get("picture")
        user.updatedAt = moment
        db.commit()

    if user is not None:
        # Ảnh Google có thể đổi sau lần đăng nhập trước; chỉ cập nhật ảnh do Google cấp.
        picture = info.get("picture")
        if (
            picture
            and picture != user.avatarUrl
            and (not user.avatarUrl or ".googleusercontent.com/" in user.avatarUrl)
        ):
            user.avatarUrl = picture
            user.updatedAt = moment
            db.commit()

    if user is None:
        name = info.get("name") or email.split("@")[0]
        user = User(
            fullName=name,
            email=email,
            googleId=google_id,
            passwordHash=hash_password(secrets.token_hex(16)),
            isVerified=True,
            emailVerifiedAt=moment,
            avatarUrl=info.get("picture"),
            createdAt=moment,
            updatedAt=moment,
        )
        db.add(user)
        db.flush()
        db.add(Wallet(userId=user.id))
        buyer_role_id = _buyer_role_id(db)
        if buyer_role_id is not None:
            db.add(UserRole(userId=user.id, roleId=buyer_role_id))
        db.commit()

    if user.status == "BANNED":
        raise ApiError(403, "Tài khoản đã bị khóa")

    return _auth_payload(db, user)


@router.get("/me")
def me(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    row = db.execute(select(User).where(User.id == user.id)).scalar_one()
    profile = db.execute(select(SellerProfile).where(SellerProfile.userId == user.id)).scalar_one_or_none()
    wallet = db.execute(select(Wallet.balance, Wallet.pendingBalance).where(Wallet.userId == user.id)).first()

    # Prisma trả toàn bộ cột trừ các cột bí mật (src/routes/auth.js:207).
    safe = to_dict(row, exclude=("passwordHash", "passwordResetTokenHash", "passwordResetExpiresAt"))
    safe.pop("emailVerificationTokenHash", None)
    safe.pop("emailVerificationExpiresAt", None)
    safe["roles"] = _roles_of(db, user.id)
    safe["sellerProfile"] = to_dict(profile) if profile else None
    safe["wallet"] = {"balance": wallet.balance, "pendingBalance": wallet.pendingBalance} if wallet else None
    return safe


@router.post("/forgot-password", dependencies=[Depends(mail_limit(10))])
def forgot_password(payload: EmailIn, db: Session = Depends(get_db)):
    if not settings.is_development and not (settings.resend_api_key and settings.mail_from):
        raise ApiError(503, "Dịch vụ email chưa được cấu hình")

    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is not None:
        reset_token = secrets.token_hex(32)
        otp, otp_hash, otp_expires = _make_otp()
        user.passwordResetTokenHash = _sha256(reset_token)
        user.passwordResetExpiresAt = now() + RESET_TOKEN_TTL
        user.passwordOtpHash = otp_hash
        user.passwordOtpExpiresAt = otp_expires
        user.passwordOtpAttempts = 0
        user.updatedAt = now()
        db.commit()
        try:
            send_account_email(user.email, "reset", reset_token, otp)
        except ApiError:
            pass

    if settings.resend_api_key and settings.mail_from:
        message = "Yêu cầu đã được tiếp nhận. Nếu email tồn tại, hãy kiểm tra hộp thư để nhận link đặt lại mật khẩu."
    else:
        message = "Nếu email tồn tại, thư được lưu trong hộp thư development trên máy chủ."
    return {"message": message}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    token_hash = _sha256(payload.resetToken)
    moment = now()
    user = db.execute(
        select(User).where(User.passwordResetTokenHash == token_hash, User.passwordResetExpiresAt > moment)
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(400, "Link đặt lại đã hết hạn")

    result = db.execute(
        update(User)
        .where(User.id == user.id, User.passwordResetTokenHash == token_hash, User.passwordResetExpiresAt > moment)
        .values(
            passwordHash=hash_password(payload.newPassword),
            passwordResetTokenHash=None,
            passwordResetExpiresAt=None,
            sessionVersion=User.sessionVersion + 1,
            updatedAt=moment,
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise ApiError(400, "Link đã được sử dụng hoặc hết hạn")
    return {"message": "Đặt lại mật khẩu thành công"}


@router.get("/config")
def config():
    return {"googleClientId": settings.google_client_id or "", "emailMode": email_mode()}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailIn, db: Session = Depends(get_db)):
    result = db.execute(
        update(User)
        .where(User.emailVerificationTokenHash == _sha256(payload.token), User.emailVerificationExpiresAt > now())
        .values(
            isVerified=True,
            emailVerifiedAt=now(),
            emailVerificationTokenHash=None,
            emailVerificationExpiresAt=None,
            updatedAt=now(),
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise ApiError(400, "Link xác nhận đã sử dụng hoặc hết hạn")
    return {"message": "Đã xác nhận email thành công"}


@router.post("/resend-verification", dependencies=[Depends(mail_limit(10))])
def resend_verification(payload: EmailIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is not None and not user.emailVerifiedAt:
        token = secrets.token_hex(32)
        otp, otp_hash, otp_expires = _make_otp()
        user.emailVerificationTokenHash = _sha256(token)
        user.emailVerificationExpiresAt = now() + VERIFY_TOKEN_TTL
        user.emailOtpHash = otp_hash
        user.emailOtpExpiresAt = otp_expires
        user.emailOtpAttempts = 0
        user.updatedAt = now()
        db.commit()
        send_account_email(user.email, "verify", token, otp)
    return {"message": "Nếu tài khoản chưa xác nhận, thư xác nhận đã được tạo."}


@router.post("/verify-otp", dependencies=[Depends(mail_limit(30))])
def verify_otp(payload: OtpIn, db: Session = Depends(get_db)):
    result, user = consume_otp(db, "verify", payload.email, payload.otp)
    if not result.get("ok"):
        raise ApiError(400, result["error"])
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            isVerified=True,
            emailVerifiedAt=now(),
            emailVerificationTokenHash=None,
            emailVerificationExpiresAt=None,
            updatedAt=now(),
        )
    )
    db.commit()
    return {"message": "Đã xác nhận email thành công"}


@router.post("/reset-password-otp", dependencies=[Depends(mail_limit(30))])
def reset_password_otp(payload: ResetPasswordOtpIn, db: Session = Depends(get_db)):
    result, user = consume_otp(db, "reset", payload.email, payload.otp)
    if not result.get("ok"):
        raise ApiError(400, result["error"])
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            passwordHash=hash_password(payload.newPassword),
            passwordResetTokenHash=None,
            passwordResetExpiresAt=None,
            sessionVersion=User.sessionVersion + 1,
            updatedAt=now(),
        )
    )
    db.commit()
    return {"message": "Đặt lại mật khẩu thành công"}


@router.post("/logout")
def logout(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(
        update(User).where(User.id == user.id).values(sessionVersion=User.sessionVersion + 1, updatedAt=now())
    )
    db.commit()
    return {"message": "Đã đăng xuất và thu hồi các phiên đăng nhập."}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(select(User).where(User.id == user.id)).scalar_one()
    if not verify_password(payload.currentPassword, row.passwordHash):
        raise ApiError(400, "Mật khẩu hiện tại chưa đúng")

    moment = now()
    result = db.execute(
        update(User)
        .where(User.id == row.id, User.passwordHash == row.passwordHash)
        .values(
            passwordHash=hash_password(payload.newPassword),
            sessionVersion=User.sessionVersion + 1,
            passwordResetTokenHash=None,
            passwordResetExpiresAt=None,
            updatedAt=moment,
        )
    )
    db.commit()
    if result.rowcount == 0:
        raise ApiError(409, "Tài khoản vừa thay đổi, hãy đăng nhập lại")
    return {"message": "Đã đổi mật khẩu và thu hồi các phiên. Hãy đăng nhập lại."}
