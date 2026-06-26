from datetime import datetime

from pydantic import BaseModel, Field


class ComplianceReportRequest(BaseModel):
    product_id: str
    sections: list[str] = Field(default_factory=list)


class ComplianceCheck(BaseModel):
    key: str
    label: str
    status: str
    evidence: str
    recommendation: str


class ComplianceReportResponse(BaseModel):
    product_id: str
    product_name: str
    readiness_score: int
    summary: str
    sections: list[str]
    checks: list[ComplianceCheck]
    markdown: str
    report_json: dict


class ProfessionalReportPackCreate(ComplianceReportRequest):
    report_type: str = Field(default="standard", pattern="^(standard|india)$")
    title: str | None = Field(default=None, max_length=180)


class ProfessionalReportPackRead(BaseModel):
    id: str
    organization_id: str
    product_id: str
    product_name: str
    created_by_user_id: str | None
    report_type: str
    title: str
    readiness_score: int
    summary: str
    sections_json: list
    checks_json: list
    report_json: dict
    markdown: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfessionalReportPackList(BaseModel):
    items: list[ProfessionalReportPackRead]
    total: int
