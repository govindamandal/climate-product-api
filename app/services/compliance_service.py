from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.compliance import ComplianceCheck, ComplianceReportRequest, ComplianceReportResponse
from app.services.product_service import ProductService

DEFAULT_SECTIONS = [
    "product_identity",
    "environmental_metrics",
    "materials",
    "certifications",
    "dpp_readiness",
]


class ComplianceReportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, user: User, payload: ComplianceReportRequest) -> ComplianceReportResponse:
        product = ProductService(self.db).get_product(user, payload.product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        sections = payload.sections or DEFAULT_SECTIONS
        checks = [
            ComplianceCheck(
                key="product_identity",
                label="Product identity",
                status="ready" if all([product.name, product.category, product.manufacturer, product.country]) else "needs_review",
                evidence=f"{product.name} by {product.manufacturer}, {product.country}",
                recommendation="Keep manufacturer, category, country, and production method current.",
            ),
            ComplianceCheck(
                key="environmental_metrics",
                label="Environmental metrics",
                status="ready" if latest else "missing",
                evidence=(
                    f"{latest.co2_kg} kg CO2e, {latest.water_liters} L water, {latest.energy_kwh} kWh energy"
                    if latest
                    else "No environmental record is available."
                ),
                recommendation="Attach verified LCA/EPD metrics for CO2e, water, energy, transport, and recyclability.",
            ),
            ComplianceCheck(
                key="materials",
                label="Material composition",
                status="ready" if product.material_composition else "needs_review",
                evidence=", ".join(product.material_composition.keys()) if product.material_composition else "No material composition fields.",
                recommendation="Provide material composition percentages and recycled/renewable content where available.",
            ),
            ComplianceCheck(
                key="certifications",
                label="Certifications",
                status="ready" if product.certifications else "needs_review",
                evidence=f"{len(product.certifications)} certification record(s)",
                recommendation="Upload EPDs and third-party certificates with expiry dates and declaration numbers.",
            ),
            ComplianceCheck(
                key="dpp_readiness",
                label="Digital Product Passport readiness",
                status="ready" if latest and product.material_composition else "needs_review",
                evidence=f"Sustainability score {latest.sustainability_score}/100" if latest else "Passport lacks measured environmental data.",
                recommendation="Complete environmental metrics and material composition before buyer-facing DPP export.",
            ),
        ]
        selected_checks = [check for check in checks if check.key in sections]
        readiness_score = round(
            sum(status_points(check.status) for check in selected_checks) / max(len(selected_checks), 1)
        )
        summary = summarize_report(product.name, readiness_score, selected_checks)
        report_json = {
            "schema": "compliance-report.v1",
            "generated_at": datetime.utcnow().isoformat(),
            "product": {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "manufacturer": product.manufacturer,
                "country": product.country,
            },
            "readiness_score": readiness_score,
            "summary": summary,
            "sections": sections,
            "checks": [check.model_dump() for check in selected_checks],
        }
        markdown = build_markdown(report_json)
        return ComplianceReportResponse(
            product_id=product.id,
            product_name=product.name,
            readiness_score=readiness_score,
            summary=summary,
            sections=sections,
            checks=selected_checks,
            markdown=markdown,
            report_json=report_json,
        )


def status_points(status: str) -> int:
    if status == "ready":
        return 100
    if status == "needs_review":
        return 60
    return 0


def summarize_report(product_name: str, readiness_score: int, checks: list[ComplianceCheck]) -> str:
    missing = [check.label for check in checks if check.status != "ready"]
    if not missing:
        return f"{product_name} is compliance-ready for DPP and sustainability report review."
    return f"{product_name} is {readiness_score}% ready. Review required for: {', '.join(missing)}."


def build_markdown(report: dict) -> str:
    lines = [
        "# Compliance Readiness Report",
        "",
        f"Product: {report['product']['name']}",
        f"Manufacturer: {report['product']['manufacturer']}",
        f"Readiness score: {report['readiness_score']}/100",
        "",
        "## Executive summary",
        "",
        report["summary"],
        "",
        "## Compliance checks",
        "",
    ]
    for check in report["checks"]:
        lines.extend(
            [
                f"### {check['label']} - {check['status'].replace('_', ' ').title()}",
                "",
                f"Evidence: {check['evidence']}",
                "",
                f"Recommendation: {check['recommendation']}",
                "",
            ]
        )
    return "\n".join(lines)
