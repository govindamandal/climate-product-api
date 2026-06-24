from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import PasswordResetToken, RefreshToken, User
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, User)

    def by_email(self, email: str, organization_id: str | None = None) -> User | None:
        stmt = select(User).where(User.email == email)
        if organization_id:
            stmt = stmt.where(User.organization_id == organization_id)
        return self.db.scalar(stmt)

    def by_email_all(self, email: str) -> list[User]:
        return list(self.db.scalars(select(User).where(User.email == email)))

    def members(self, organization_id: str) -> list[User]:
        return list(self.db.scalars(select(User).where(User.organization_id == organization_id)))


class RefreshTokenRepository(Repository[RefreshToken]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, RefreshToken)

    def by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def active_for_user(self, user_id: str) -> list[RefreshToken]:
        return list(
            self.db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )


class PasswordResetTokenRepository(Repository[PasswordResetToken]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, PasswordResetToken)

    def by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self.db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
