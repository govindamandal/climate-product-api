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
