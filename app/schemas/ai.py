from pydantic import BaseModel


class Recommendation(BaseModel):
    title: str
    category: str
    impact: str
    rationale: str
    next_step: str


class AISafetyMetadata(BaseModel):
    status: str
    provider: str
    execution_mode: str
    policy_version: str = "ai-safety.v1"
    data_policy: str
    validation_notes: list[str] = []
    disclaimers: list[str] = []


class AdvisorResponse(BaseModel):
    product_id: str
    provider: str
    safety: AISafetyMetadata
    recommendations: list[Recommendation]


class ReportResponse(BaseModel):
    product_id: str
    provider: str
    safety: AISafetyMetadata
    summary: str
    markdown: str


class AIJobRead(BaseModel):
    id: str
    organization_id: str
    product_id: str
    job_type: str
    status: str
    provider: str | None = None
    safety_status: str | None = None
    safety_metadata_json: dict | None = None
    result_json: dict | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
