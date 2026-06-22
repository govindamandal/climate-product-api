from datetime import datetime, timedelta

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
from app.models.user import RefreshToken, User
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import RefreshTokenRepository, UserRepository
from app.schemas.auth import AuthTokens, LoginRequest, RegisterRequest
from app.services.audit_service import AuditService


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
