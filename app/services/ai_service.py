from sqlalchemy.orm import Session

from app.schemas.ai import AdvisorResponse, Recommendation, ReportResponse
from app.services.product_service import ProductService


class SustainabilityAdvisor:
    provider_name = "local"

    def __init__(self, db: Session) -> None:
        self.db = db

    def analyze(self, user, product_id: str) -> AdvisorResponse:
        product = ProductService(self.db).get_product(user, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        recommendations: list[Recommendation] = []
        if not latest:
            recommendations.append(
                Recommendation(
                    title="Add verified environmental measurements",
                    category="data_quality",
                    impact="High",
                    rationale="Recommendations improve once product-specific LCA data exists.",
                    next_step="Upload an EPD or add a measured environmental record.",
                )
            )
        else:
            if latest.transportation_kg_co2 > latest.co2_kg * 0.18:
                recommendations.append(
                    Recommendation(
                        title="Reduce transportation intensity",
                        category="logistics",
                        impact="Medium",
                        rationale="Transportation is a material share of the carbon footprint.",
                        next_step="Model regional supplier routing and increase rail freight share.",
                    )
                )
            if latest.energy_kwh > 500:
                recommendations.append(
                    Recommendation(
                        title="Shift high-temperature process energy",
                        category="manufacturing",
                        impact="High",
                        rationale="Energy demand is above the portfolio median for this class.",
                        next_step="Evaluate renewable PPAs and heat recovery on the production line.",
                    )
                )
            if latest.recyclability_score < 70:
                recommendations.append(
                    Recommendation(
                        title="Improve end-of-life circularity",
                        category="materials",
                        impact="Medium",
                        rationale="Lower recyclability weakens passport readiness and buyer scoring.",
                        next_step="Assess binders, additives, and take-back routes with procurement.",
                    )
                )
        return AdvisorResponse(
            product_id=product_id,
            provider=self.provider_name,
            recommendations=recommendations[:5],
        )

    def report(self, user, product_id: str) -> ReportResponse:
        product = ProductService(self.db).get_product(user, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        if latest:
            summary = (
                f"{product.name} records {latest.co2_kg:.1f} kg CO2e with energy and "
                f"transportation as primary optimization levers."
            )
        else:
            summary = f"{product.name} needs verified environmental data before benchmarking."
        markdown = f"# Sustainability Executive Summary\n\n{summary}\n\n## Recommended focus\n\n"
        markdown += "- Validate source EPD data\n- Prioritize energy intensity reductions\n- Review logistics footprint\n"
        return ReportResponse(product_id=product_id, summary=summary, markdown=markdown)
