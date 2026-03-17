"""
UserService — business logic for user management.

Rules enforced here (not in the router):
  - Cannot delete / lock / reset-password of SUPER_ADMIN
  - Only super admin can act on other admins
  - Cannot act on yourself (delete/lock)
"""
import secrets
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User, SUPER_ADMIN_USERNAME
from schemas.user import UserCreate, UserUpdate
from core.security import hash_password, verify_password


class UserService:

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def get_all(db: Session) -> list[User]:
        return db.query(User).order_by(User.created_at.desc()).all()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_username_or_email(db: Session, identifier: str) -> Optional[User]:
        return (
            db.query(User)
            .filter((User.username == identifier) | (User.email == identifier))
            .first()
        )

    # ── Auth ──────────────────────────────────────────────────────────────────

    @staticmethod
    def authenticate(db: Session, identifier: str, password: str) -> Optional[User]:
        """Return user if credentials valid and account active, else None."""
        user = UserService.get_by_username_or_email(db, identifier)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        user.last_login = datetime.utcnow()
        db.commit()
        return user

    # ── Create ────────────────────────────────────────────────────────────────

    @staticmethod
    def create(db: Session, data: UserCreate) -> tuple[Optional[User], Optional[str]]:
        """
        Create a new user.
        Returns (user, None) on success, (None, error_message) on failure.
        """
        if db.query(User).filter(User.username == data.username).first():
            return None, f"Username '{data.username}' đã tồn tại."
        if db.query(User).filter(User.email == data.email).first():
            return None, f"Email '{data.email}' đã được sử dụng."

        user = User(
            username=data.username,
            email=data.email.lower(),
            full_name=data.full_name or None,
            hashed_password=hash_password(data.password),
            is_active=True,
            is_admin=data.is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user, None

    # ── Delete ────────────────────────────────────────────────────────────────

    @staticmethod
    def delete(
        db: Session,
        target: User,
        actor_username: str,
        actor_is_super: bool,
    ) -> Optional[str]:
        """
        Delete a user. Returns None on success, error string on failure.
        Sets is_active=False first so the middleware kicks them immediately.
        """
        err = UserService._guard(target, actor_username, actor_is_super, "xóa")
        if err:
            return err

        target.is_active = False
        db.commit()
        db.delete(target)
        db.commit()
        return None

    # ── Toggle active ─────────────────────────────────────────────────────────

    @staticmethod
    def toggle_active(
        db: Session,
        target: User,
        actor_username: str,
        actor_is_super: bool,
    ) -> tuple[Optional[User], Optional[str]]:
        """Toggle is_active. Returns (updated_user, None) or (None, error)."""
        action = "khoá" if target.is_active else "mở khoá"
        err = UserService._guard(target, actor_username, actor_is_super, action)
        if err:
            return None, err

        target.is_active = not target.is_active
        db.commit()
        db.refresh(target)
        return target, None

    # ── Reset password ────────────────────────────────────────────────────────

    @staticmethod
    def reset_password(
        db: Session,
        target: User,
        actor_username: str,
        actor_is_super: bool,
        new_password: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Reset user password.
        Pass new_password=None to auto-generate.
        Returns (plain_password, None) on success, (None, error) on failure.
        """
        err = UserService._guard(target, actor_username, actor_is_super, "reset mật khẩu")
        if err:
            return None, err

        plain = new_password or UserService._generate_password()
        target.hashed_password = hash_password(plain)

        # Force-kick active session: middleware checks is_active on every request
        target.is_active = False
        db.commit()
        target.is_active = True
        db.commit()

        return plain, None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _guard(
        target: User,
        actor_username: str,
        actor_is_super: bool,
        action: str,
    ) -> Optional[str]:
        """Return an error string if the action is not permitted, else None."""
        if target.username == actor_username:
            return f"Không thể {action} tài khoản của chính mình."
        if target.username == SUPER_ADMIN_USERNAME:
            return f"Không thể {action} tài khoản Super Admin."
        if target.is_admin and not actor_is_super:
            return f"Chỉ Super Admin mới có thể {action} tài khoản Admin khác."
        return None

    @staticmethod
    def _generate_password(length: int = 12) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        return "".join(secrets.choice(alphabet) for _ in range(length))