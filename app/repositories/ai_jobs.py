from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.repositories.base import Repository


class AIJobRepository(Repository[AIJob]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, AIJob)

    def get_for_org(self, organization_id: str, job_id: str) -> AIJob | None:
        return self.db.scalar(
            select(AIJob).where(AIJob.organization_id == organization_id, AIJob.id == job_id)
        )
