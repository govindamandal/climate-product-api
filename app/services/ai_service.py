import json
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException
import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.ai_job import AIJob
from app.models.organization import OrganizationPrivacySettings
from app.models.product import EnvironmentalRecord, Product
from app.models.user import User
from app.repositories.ai_jobs import AIJobRepository
from app.repositories.products import ProductRepository
from app.schemas.ai import AISafetyMetadata, AIJobRead, AdvisorResponse, Recommendation, ReportResponse
from app.services.product_service import ProductService

AI_DISCLOSURES = [
    "AI outputs are decision-support only and must be reviewed by a qualified sustainability or compliance owner.",
    "Recommendations are not third-party verified EPD, LCA, or regulatory certification conclusions.",
]


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
        parsed = _parse_recommendations(items)
        return parsed or fallback

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        payload = self._complete_json(
            "Return JSON with summary and markdown fields for an executive sustainability report.",
            _product_prompt(product, latest),
        )
        summary = str(payload.get("summary") or fallback.summary)
        markdown = str(payload.get("markdown") or fallback.markdown)
        return ReportResponse(
            product_id=product.id,
            provider=self.name,
            safety=_safety_metadata(self.name, fallback_used=not payload),
            summary=summary,
            markdown=markdown,
        )

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
        parsed = _parse_recommendations(items)
        return parsed or fallback

    def report(self, product: Product, latest: EnvironmentalRecord | None, fallback: ReportResponse) -> ReportResponse:
        payload = self._complete_json(
            "Return only JSON with summary and markdown fields for an executive sustainability report.",
            _product_prompt(product, latest),
        )
        summary = str(payload.get("summary") or fallback.summary)
        markdown = str(payload.get("markdown") or fallback.markdown)
        return ReportResponse(
            product_id=product.id,
            provider=self.name,
            safety=_safety_metadata(self.name, fallback_used=not payload),
            summary=summary,
            markdown=markdown,
        )

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
        if not user.organization_id:
            raise HTTPException(status_code=403, detail="Organization context required")
        return self.analyze_for_org(user.organization_id, product_id)

    def analyze_for_org(self, organization_id: str, product_id: str) -> AdvisorResponse:
        self._assert_ai_allowed(organization_id)
        product = self._get_product_for_org(organization_id, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        fallback = _local_recommendations(latest)
        recommendations = self.provider.recommendations(
            product, latest, fallback
        )
        return AdvisorResponse(
            product_id=product_id,
            provider=self.provider.name,
            safety=_safety_metadata(self.provider.name, fallback_used=recommendations == fallback),
            recommendations=recommendations[:5],
        )

    def report(self, user, product_id: str) -> ReportResponse:
        if not user.organization_id:
            raise HTTPException(status_code=403, detail="Organization context required")
        return self.report_for_org(user.organization_id, product_id)

    def report_for_org(self, organization_id: str, product_id: str) -> ReportResponse:
        self._assert_ai_allowed(organization_id)
        product = self._get_product_for_org(organization_id, product_id)
        latest = product.environmental_records[0] if product.environmental_records else None
        fallback = _local_report(product, latest)
        report = self.provider.report(product, latest, fallback)
        return ReportResponse(
            product_id=product.id,
            provider=report.provider,
            safety=report.safety,
            summary=report.summary,
            markdown=_append_ai_disclaimer(report.markdown, report.safety),
        )

    def _get_product_for_org(self, organization_id: str, product_id: str) -> Product:
        product = ProductRepository(self.db).get_for_org(organization_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    def _assert_ai_allowed(self, organization_id: str) -> None:
        settings = self.db.scalar(
            select(OrganizationPrivacySettings).where(
                OrganizationPrivacySettings.organization_id == organization_id
            )
        )
        if settings and not settings.allow_ai_processing:
            raise HTTPException(status_code=403, detail="AI processing is disabled for this organization")


class AIJobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = AIJobRepository(db)

    def enqueue(self, user: User, product_id: str, job_type: str) -> AIJobRead:
        if not user.organization_id:
            raise HTTPException(status_code=403, detail="Organization context required")
        if job_type not in {"advisor", "report"}:
            raise HTTPException(status_code=400, detail="Unsupported AI job type")
        ProductService(self.db).get_product(user, product_id)
        SustainabilityAdvisor(self.db)._assert_ai_allowed(user.organization_id)
        provider = build_ai_provider().name
        job = AIJob(
            organization_id=user.organization_id,
            user_id=user.id,
            product_id=product_id,
            job_type=job_type,
            status="pending",
            provider=provider,
            safety_status="pending_review",
            safety_metadata_json=_safety_metadata(provider).model_dump(mode="json"),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return AIJobRead.model_validate(job)

    def get_job(self, user: User, job_id: str) -> AIJobRead:
        if not user.organization_id:
            raise HTTPException(status_code=403, detail="Organization context required")
        job = self.jobs.get_for_org(user.organization_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="AI job not found")
        return AIJobRead.model_validate(job)

    @staticmethod
    def process(job_id: str) -> None:
        db = SessionLocal()
        try:
            AIJobService.process_with_session(db, job_id)
        finally:
            db.close()

    @staticmethod
    def process_with_session(db: Session, job_id: str) -> None:
        job = db.get(AIJob, job_id)
        if not job or job.status not in {"pending", "failed"}:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        try:
            advisor = SustainabilityAdvisor(db)
            if job.job_type == "advisor":
                response = advisor.analyze_for_org(job.organization_id, job.product_id)
                result = response.model_dump()
            elif job.job_type == "report":
                response = advisor.report_for_org(job.organization_id, job.product_id)
                result = response.model_dump()
            else:
                raise ValueError(f"Unsupported AI job type: {job.job_type}")
            job.result_json = result
            job.provider = result.get("provider") or advisor.provider.name
            safety = result.get("safety") or {}
            job.safety_status = str(safety.get("status") or "validated")
            job.safety_metadata_json = safety
            job.status = "succeeded"
            job.error_message = None
        except Exception as exc:  # noqa: BLE001 - job state should capture provider/runtime failures.
            job.status = "failed"
            job.safety_status = "failed"
            job.error_message = str(exc)
        job.completed_at = datetime.utcnow()
        db.commit()


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
    return ReportResponse(
        product_id=product.id,
        provider="local",
        safety=_safety_metadata("local", fallback_used=True),
        summary=summary,
        markdown=markdown,
    )


def _parse_recommendations(items: object) -> list[Recommendation]:
    if not isinstance(items, list):
        return []
    parsed: list[Recommendation] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        try:
            parsed.append(Recommendation.model_validate(item))
        except ValidationError:
            continue
    return parsed


def _safety_metadata(provider: str, *, fallback_used: bool = False) -> AISafetyMetadata:
    execution_mode = "deterministic" if provider == "local" else "provider"
    notes = ["Structured output validated with application schema."]
    if fallback_used:
        notes.append("Local deterministic fallback was used or retained.")
    return AISafetyMetadata(
        status="validated",
        provider=provider,
        execution_mode=execution_mode,
        data_policy="Organization AI processing setting is checked before product data is analyzed.",
        validation_notes=notes,
        disclaimers=AI_DISCLOSURES,
    )


def _append_ai_disclaimer(markdown: str, safety: AISafetyMetadata) -> str:
    if "## AI Safety Notes" in markdown:
        return markdown
    notes = "\n".join(f"- {item}" for item in safety.disclaimers)
    return f"{markdown.rstrip()}\n\n## AI Safety Notes\n\n{notes}\n"


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
