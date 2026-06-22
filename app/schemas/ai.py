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
