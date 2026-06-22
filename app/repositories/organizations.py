from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.repositories.base import Repository


class OrganizationRepository(Repository[Organization]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Organization)

    def by_slug(self, slug: str) -> Organization | None:
        return self.db.scalar(select(Organization).where(Organization.slug == slug))
