from fastapi import APIRouter, BackgroundTasks

from app.api.deps import CurrentUser, DbSession
from app.schemas.ai import AIJobRead, AdvisorResponse, ReportResponse
from app.services.ai_service import AIJobService, SustainabilityAdvisor

router = APIRouter(prefix="/ai", tags=["AI Sustainability"])


@router.post("/products/{product_id}/advisor", response_model=AdvisorResponse)
def product_advisor(product_id: str, user: CurrentUser, db: DbSession) -> AdvisorResponse:
    return SustainabilityAdvisor(db).analyze(user, product_id)


@router.post("/products/{product_id}/report", response_model=ReportResponse)
def product_report(product_id: str, user: CurrentUser, db: DbSession) -> ReportResponse:
    return SustainabilityAdvisor(db).report(user, product_id)


@router.post("/products/{product_id}/advisor/jobs", response_model=AIJobRead, status_code=202)
def enqueue_product_advisor(
    product_id: str, background_tasks: BackgroundTasks, user: CurrentUser, db: DbSession
) -> AIJobRead:
    job = AIJobService(db).enqueue(user, product_id, "advisor")
    background_tasks.add_task(AIJobService.process_with_session, db, job.id)
    return job


@router.post("/products/{product_id}/report/jobs", response_model=AIJobRead, status_code=202)
def enqueue_product_report(
    product_id: str, background_tasks: BackgroundTasks, user: CurrentUser, db: DbSession
) -> AIJobRead:
    job = AIJobService(db).enqueue(user, product_id, "report")
    background_tasks.add_task(AIJobService.process_with_session, db, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=AIJobRead)
def get_ai_job(job_id: str, user: CurrentUser, db: DbSession) -> AIJobRead:
    return AIJobService(db).get_job(user, job_id)
