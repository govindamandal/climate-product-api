from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.verification import ProductVerification
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

INDIA_SECTIONS = [
    "india_product_identity",
    "india_environmental_disclosure",
    "india_material_traceability",
    "india_certifications",
    "india_verification",
    "india_buyer_pack",
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

    def build_india_readiness(self, user: User, payload: ComplianceReportRequest) -> ComplianceReportResponse:
        product = ProductService(self.db).get_product(user, payload.product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        approved_verification = self.db.scalar(
            select(ProductVerification)
            .where(
                ProductVerification.organization_id == product.organization_id,
                ProductVerification.product_id == product.id,
                ProductVerification.status == "approved",
            )
            .order_by(ProductVerification.reviewed_at.desc().nullslast(), ProductVerification.created_at.desc())
        )
        sections = payload.sections or INDIA_SECTIONS
        checks = [
            ComplianceCheck(
                key="india_product_identity",
                label="India product identity",
                status="ready" if all([product.name, product.category, product.manufacturer, product.country, product.manufacturing_site]) else "needs_review",
                evidence=(
                    f"{product.name}, {product.category}, manufacturer {product.manufacturer}, "
                    f"site {product.manufacturing_site or 'not specified'}, geography {product.geography or product.country}"
                ),
                recommendation="Maintain product SKU, manufacturing site, plant code, declared unit, and India sales/manufacturing geography for buyer and tender evidence.",
            ),
            ComplianceCheck(
                key="india_environmental_disclosure",
                label="Environmental disclosure",
                status="ready" if latest else "missing",
                evidence=(
                    f"CO2e {latest.co2_kg} kg, water {latest.water_liters} L, energy {latest.energy_kwh} kWh, transport {latest.transportation_kg_co2} kg CO2e"
                    if latest
                    else "No measured or calculated environmental record is available."
                ),
                recommendation="Capture period-specific energy, fuel, water, production volume, transport, and emissions data for BRSR/customer ESG disclosures.",
            ),
            ComplianceCheck(
                key="india_material_traceability",
                label="Material traceability",
                status="ready" if product.material_components else ("needs_review" if product.material_composition else "missing"),
                evidence=(
                    "; ".join(
                        f"{component.material_name} {component.percentage}% from {component.origin_country or 'unknown origin'}"
                        for component in product.material_components
                    )
                    if product.material_components
                    else f"Legacy material fields: {', '.join(product.material_composition.keys())}" if product.material_composition else "No material composition evidence."
                ),
                recommendation="Collect supplier declarations, recycled content, origin country, and evidence references for cement, aggregate, steel, glass, timber, and additives.",
            ),
            ComplianceCheck(
                key="india_certifications",
                label="Certificates and standards",
                status="ready" if product.certifications and product.product_standard else ("needs_review" if product.certifications or product.product_standard else "missing"),
                evidence=(
                    f"{len(product.certifications)} certificate(s), standard {product.product_standard or 'not specified'}, PCR {product.pcr or 'not specified'}"
                ),
                recommendation="Attach BIS/IS references where applicable, EPD or ISO evidence when available, expiry dates, certificate numbers, and product category rules.",
            ),
            ComplianceCheck(
                key="india_verification",
                label="Internal verification",
                status="ready" if approved_verification else "needs_review",
                evidence=(
                    f"Approved verification on {approved_verification.reviewed_at.date().isoformat() if approved_verification.reviewed_at else approved_verification.updated_at.date().isoformat()}"
                    if approved_verification
                    else "No approved product verification request is available."
                ),
                recommendation="Use the verification workflow to approve evidence before sharing DPPs, compliance reports, or buyer tender packs.",
            ),
            ComplianceCheck(
                key="india_buyer_pack",
                label="Buyer and tender pack",
                status="ready" if latest and product.certifications and approved_verification else "needs_review",
                evidence=(
                    "DPP evidence, environmental metrics, certifications, and approval trail are available."
                    if latest and product.certifications and approved_verification
                    else "Buyer-facing evidence pack is incomplete."
                ),
                recommendation="Prepare exportable DPP JSON/PDF, compliance summary, certificate pack, LCA calculation history, and audit trail for procurement teams.",
            ),
        ]
        selected_checks = [check for check in checks if check.key in sections]
        readiness_score = round(
            sum(status_points(check.status) for check in selected_checks) / max(len(selected_checks), 1)
        )
        summary = summarize_report(product.name, readiness_score, selected_checks)
        report_json = {
            "schema": "india-compliance-readiness.v1",
            "jurisdiction": "India",
            "generated_at": datetime.utcnow().isoformat(),
            "product": {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "manufacturer": product.manufacturer,
                "country": product.country,
                "manufacturing_site": product.manufacturing_site,
                "plant_code": product.plant_code,
                "declared_unit": product.declared_unit,
                "product_standard": product.product_standard,
                "pcr": product.pcr,
            },
            "readiness_score": readiness_score,
            "summary": summary,
            "sections": sections,
            "checks": [check.model_dump() for check in selected_checks],
        }
        markdown = build_markdown(report_json, title="India Compliance Readiness Report")
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


def build_markdown(report: dict, title: str = "Compliance Readiness Report") -> str:
    lines = [
        f"# {title}",
        "",
        f"Product: {report['product']['name']}",
        f"Manufacturer: {report['product']['manufacturer']}",
        *([f"Jurisdiction: {report['jurisdiction']}"] if report.get("jurisdiction") else []),
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
