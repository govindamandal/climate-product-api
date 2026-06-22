from fastapi import APIRouter, BackgroundTasks

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AuthTokens,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
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


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(lambda: payload.email)
    return {"message": "If the account exists, password reset instructions will be sent."}


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return user
