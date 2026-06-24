from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AuthTokens,
    AcceptInviteRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserRead,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthTokens, status_code=201)
def register(payload: RegisterRequest, db: DbSession) -> AuthTokens:
    return AuthService(db).register(payload)


@router.post("/login", response_model=AuthTokens)
def login(payload: LoginRequest, db: DbSession) -> AuthTokens:
    return AuthService(db).login(payload)


@router.post("/refresh", response_model=AuthTokens)
def refresh(payload: RefreshRequest, db: DbSession) -> AuthTokens:
    return AuthService(db).refresh(payload.refresh_token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse, status_code=202)
def forgot_password(payload: ForgotPasswordRequest, db: DbSession) -> ForgotPasswordResponse:
    return AuthService(db).request_password_reset(payload)


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> dict:
    return AuthService(db).reset_password(payload)


@router.post("/accept-invite", response_model=AuthTokens)
def accept_invite(payload: AcceptInviteRequest, db: DbSession) -> AuthTokens:
    return AuthService(db).accept_invite(payload)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return user
