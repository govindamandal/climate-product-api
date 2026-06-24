from datetime import datetime, timedelta
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import AuditAction, UserRole
from app.models.organization import Organization
from app.models.user import PasswordResetToken, RefreshToken, User
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import PasswordResetTokenRepository, RefreshTokenRepository, UserRepository
from app.schemas.auth import (
    AcceptInviteRequest,
    AuthTokens,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.audit_service import AuditService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def register(self, payload: RegisterRequest) -> AuthTokens:
        org_repo = OrganizationRepository(self.db)
        if org_repo.by_slug(payload.organization_slug):
            raise HTTPException(status_code=409, detail="Organization slug is already in use")

        org = Organization(
            name=payload.organization_name,
            slug=payload.organization_slug,
            country=payload.country,
        )
        self.db.add(org)
        self.db.flush()
        user = User(
            organization_id=org.id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=UserRole.ORG_ADMIN,
        )
        self.db.add(user)
        self.db.flush()
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="organization",
            organization_id=org.id,
            actor_user_id=user.id,
            entity_id=org.id,
        )
        self.db.commit()
        return self._issue_tokens(user)

    def login(self, payload: LoginRequest) -> AuthTokens:
        org_id = None
        if payload.organization_slug:
            org = OrganizationRepository(self.db).by_slug(payload.organization_slug)
            if not org:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login")
            org_id = org.id
        user = UserRepository(self.db).by_email(payload.email, org_id)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login")
        AuditService(self.db).record(
            action=AuditAction.LOGIN,
            entity_type="user",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=user.id,
        )
        self.db.commit()
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> AuthTokens:
        token = RefreshTokenRepository(self.db).by_hash(hash_token(refresh_token))
        if not token or token.revoked_at or token.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        token.revoked_at = datetime.utcnow()
        self.db.flush()
        self.db.commit()
        return self._issue_tokens(token.user)

    def request_password_reset(self, payload: ForgotPasswordRequest) -> ForgotPasswordResponse:
        user = self._resolve_reset_user(payload)
        message = "If the account exists, password reset instructions will be sent."
        if not user or not user.is_active:
            return ForgotPasswordResponse(message=message)

        reset_url = self.create_password_reset_url(user, purpose="password_reset")
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="password_reset",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=user.id,
        )
        self.db.commit()
        logger.info("password_reset_requested", extra={"user_id": user.id, "reset_url": reset_url})
        EmailService().send_password_reset(
            to_email=user.email,
            full_name=user.full_name,
            reset_url=reset_url,
        )
        if self.settings.environment in {"local", "development", "test"}:
            return ForgotPasswordResponse(message=message, reset_url=reset_url)
        return ForgotPasswordResponse(message=message)

    def reset_password(self, payload: ResetPasswordRequest) -> dict:
        reset_token, user = self._consume_password_token(payload.token, purpose="password_reset")
        user.hashed_password = hash_password(payload.password)
        refresh_tokens = RefreshTokenRepository(self.db).active_for_user(user.id)
        for token in refresh_tokens:
            token.revoked_at = datetime.utcnow()
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="password",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=user.id,
        )
        self.db.commit()
        return {"message": "Password has been reset. Please sign in with your new password."}

    def accept_invite(self, payload: AcceptInviteRequest) -> AuthTokens:
        _, user = self._consume_password_token(payload.token, purpose="invite_accept")
        user.hashed_password = hash_password(payload.password)
        user.is_active = True
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="invite_acceptance",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=user.id,
        )
        self.db.commit()
        return self._issue_tokens(user)

    def create_password_reset_url(self, user: User, *, purpose: str = "password_reset") -> str:
        raw_token, token_hash = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(minutes=self.settings.password_reset_token_expire_minutes)
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                purpose=purpose,
                expires_at=expires_at,
            )
        )
        path = "accept-invite" if purpose == "invite_accept" else "reset-password"
        return f"{self.settings.frontend_base_url.rstrip('/')}/{path}?token={raw_token}"

    def _consume_password_token(self, raw_token: str, *, purpose: str) -> tuple[PasswordResetToken, User]:
        token = PasswordResetTokenRepository(self.db).by_hash(hash_token(raw_token))
        if (
            not token
            or token.purpose != purpose
            or token.used_at
            or token.expires_at < datetime.utcnow()
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        user = token.user
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        token.used_at = datetime.utcnow()
        return token, user

    def _resolve_reset_user(self, payload: ForgotPasswordRequest) -> User | None:
        user_repo = UserRepository(self.db)
        if payload.organization_slug:
            org = OrganizationRepository(self.db).by_slug(payload.organization_slug)
            if not org:
                return None
            return user_repo.by_email(payload.email, org.id)
        matches = user_repo.by_email_all(payload.email)
        if len(matches) != 1:
            return None
        return matches[0]

    def _issue_tokens(self, user: User) -> AuthTokens:
        access_token = create_access_token(
            subject=user.id,
            organization_id=user.organization_id,
            role=user.role.value,
        )
        raw_refresh, token_hash = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(days=self.settings.refresh_token_expire_days)
        self.db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        self.db.commit()
        self.db.refresh(user)
        return AuthTokens(access_token=access_token, refresh_token=raw_refresh, user=user)
