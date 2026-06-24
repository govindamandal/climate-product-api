from pydantic import BaseModel


class Recommendation(BaseModel):
    title: str
    category: str
    impact: str
    rationale: str
    next_step: str


class AdvisorResponse(BaseModel):
    product_id: str
    provider: str
    recommendations: list[Recommendation]


class ReportResponse(BaseModel):
    product_id: str
    summary: str
    markdown: str


class AIJobRead(BaseModel):
    id: str
    organization_id: str
    product_id: str
    job_type: str
    status: str
    result_json: dict | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
