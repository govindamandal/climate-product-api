import json
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.product import EnvironmentalRecord, Product
from app.schemas.ai import AdvisorResponse, Recommendation, ReportResponse
from app.services.product_service import ProductService


class AIProvider(Protocol):
    name: str

    def recommendations(
        self, product: Product, latest: EnvironmentalRecord | None, fallback: list[Recommendation]
    ) -> list[Recommendation]:
        ...

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        ...


class LocalAIProvider:
    name = "local"

    def recommendations(
        self, product: Product, latest: EnvironmentalRecord | None, fallback: list[Recommendation]
    ) -> list[Recommendation]:
        return fallback

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        return fallback


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def recommendations(
        self, product: Product, latest: EnvironmentalRecord | None, fallback: list[Recommendation]
    ) -> list[Recommendation]:
        payload = self._complete_json(
            "Return JSON with a recommendations array. Each item must include title, category, impact, rationale, next_step.",
            _product_prompt(product, latest),
        )
        items = payload.get("recommendations", [])
        parsed = [Recommendation(**item) for item in items[:5] if isinstance(item, dict)]
        return parsed or fallback

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        payload = self._complete_json(
            "Return JSON with summary and markdown fields for an executive sustainability report.",
            _product_prompt(product, latest),
        )
        summary = str(payload.get("summary") or fallback.summary)
        markdown = str(payload.get("markdown") or fallback.markdown)
        return ReportResponse(product_id=product.id, summary=summary, markdown=markdown)

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.settings.openai_api_key:
            return {}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(
                    f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                    json={
                        "model": self.settings.ai_model,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValueError):
            return {}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def recommendations(
        self, product: Product, latest: EnvironmentalRecord | None, fallback: list[Recommendation]
    ) -> list[Recommendation]:
        payload = self._complete_json(
            "Return only JSON with a recommendations array. Each item must include title, category, impact, rationale, next_step.",
            _product_prompt(product, latest),
        )
        items = payload.get("recommendations", [])
        parsed = [Recommendation(**item) for item in items[:5] if isinstance(item, dict)]
        return parsed or fallback

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        payload = self._complete_json(
            "Return only JSON with summary and markdown fields for an executive sustainability report.",
            _product_prompt(product, latest),
        )
        summary = str(payload.get("summary") or fallback.summary)
        markdown = str(payload.get("markdown") or fallback.markdown)
        return ReportResponse(product_id=product.id, summary=summary, markdown=markdown)

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.settings.anthropic_api_key:
            return {}
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(
                    f"{self.settings.anthropic_base_url.rstrip('/')}/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 1200,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                response.raise_for_status()
            text = response.json()["content"][0]["text"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValueError):
            return {}


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    provider = settings.ai_provider.lower().strip()
    if provider in {"openai", "openai-compatible"} and settings.openai_api_key:
        return OpenAICompatibleProvider(settings)
    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider(settings)
    return LocalAIProvider()


class SustainabilityAdvisor:
    def __init__(self, db: Session, provider: AIProvider | None = None) -> None:
        self.db = db
        self.provider = provider or build_ai_provider()

    def analyze(self, user, product_id: str) -> AdvisorResponse:
        product = ProductService(self.db).get_product(user, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        recommendations = self.provider.recommendations(
            product, latest, _local_recommendations(latest)
        )
        return AdvisorResponse(
            product_id=product_id,
            provider=self.provider.name,
            recommendations=recommendations[:5],
        )

    def report(self, user, product_id: str) -> ReportResponse:
        product = ProductService(self.db).get_product(user, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        return self.provider.report(product, latest, _local_report(product, latest))


def _local_recommendations(latest: EnvironmentalRecord | None) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    if not latest:
        return [
            Recommendation(
                title="Add verified environmental measurements",
                category="data_quality",
                impact="High",
                rationale="Recommendations improve once product-specific LCA data exists.",
                next_step="Upload an EPD or add a measured environmental record.",
            )
        ]
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
    return recommendations


def _local_report(product: Product, latest: EnvironmentalRecord | None) -> ReportResponse:
    if latest:
        summary = (
            f"{product.name} records {latest.co2_kg:.1f} kg CO2e with energy and "
            f"transportation as primary optimization levers."
        )
    else:
        summary = f"{product.name} needs verified environmental data before benchmarking."
    markdown = f"# Sustainability Executive Summary\n\n{summary}\n\n## Recommended focus\n\n"
    markdown += "- Validate source EPD data\n- Prioritize energy intensity reductions\n- Review logistics footprint\n"
    return ReportResponse(product_id=product.id, summary=summary, markdown=markdown)


def _product_prompt(product: Product, latest: EnvironmentalRecord | None) -> str:
    metrics = "No environmental record available."
    if latest:
        metrics = (
            f"CO2e: {latest.co2_kg} kg; water: {latest.water_liters} L; "
            f"energy: {latest.energy_kwh} kWh; transportation: {latest.transportation_kg_co2} kg CO2e; "
            f"recyclability: {latest.recyclability_score}/100; sustainability score: {latest.sustainability_score}/100."
        )
    return (
        f"Product: {product.name}\n"
        f"Category: {product.category}\n"
        f"Manufacturer: {product.manufacturer}\n"
        f"Country: {product.country}\n"
        f"Production method: {product.production_method}\n"
        f"Description: {product.description}\n"
        f"Metrics: {metrics}"
    )
