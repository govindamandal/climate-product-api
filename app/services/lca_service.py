from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.lca import EmissionFactor, LcaCalculation
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.lca import (
    EmissionFactorRead,
    LcaCalculationCreate,
    LcaCalculationList,
)
from app.services.audit_service import AuditService

STAGES = ("A1-A3", "A4", "A5", "B", "C", "D")


class LcaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_factors(
        self,
        user: User,
        *,
        category: str | None = None,
        stage: str | None = None,
        search: str | None = None,
    ) -> list[EmissionFactorRead]:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        filters = [
            or_(
                EmissionFactor.organization_id.is_(None),
                EmissionFactor.organization_id == user.organization_id,
            )
        ]
        if category:
            filters.append(EmissionFactor.category == category)
        if stage:
            filters.append(EmissionFactor.lifecycle_stage == stage)
        if search:
            like = f"%{search}%"
            filters.append(
                EmissionFactor.name.ilike(like)
                | EmissionFactor.category.ilike(like)
                | EmissionFactor.source.ilike(like)
            )
        stmt = select(EmissionFactor).where(*filters).order_by(
            EmissionFactor.category.asc(), EmissionFactor.name.asc()
        )
        return [EmissionFactorRead.model_validate(item) for item in self.db.scalars(stmt)]

    def create_calculation(
        self, user: User, product_id: str, payload: LcaCalculationCreate
    ) -> LcaCalculation:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        product = ProductRepository(self.db).get_for_org(user.organization_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        factor_ids = [item.emission_factor_id for item in payload.inputs if item.emission_factor_id]
        factors = self._load_factors(user.organization_id, factor_ids)
        stage_totals = {stage: 0.0 for stage in STAGES}
        calculated_inputs = []
        quality_rank = {"measured": 3, "hybrid": 2, "estimated": 1}
        confidence_floor = 3

        for item in payload.inputs:
            factor = factors.get(item.emission_factor_id or "")
            factor_value = item.emission_factor_kg_co2e
            factor_name = "Custom factor"
            factor_source = "User supplied"
            factor_version = payload.method_version
            if factor:
                factor_value = factor.factor_kg_co2e
                factor_name = factor.name
                factor_source = factor.source
                factor_version = factor.version
                if factor.unit != item.unit:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Input unit {item.unit} does not match factor unit {factor.unit}",
                    )
            if factor_value is None:
                raise HTTPException(status_code=400, detail="Missing emission factor value")

            kg_co2e = round(item.quantity * factor_value, 3)
            stage_totals[item.stage] = round(stage_totals[item.stage] + kg_co2e, 3)
            confidence_floor = min(confidence_floor, quality_rank[item.data_quality])
            calculated_inputs.append(
                {
                    "stage": item.stage,
                    "activity_name": item.activity_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "emission_factor_id": item.emission_factor_id,
                    "emission_factor_name": factor_name,
                    "emission_factor_kg_co2e": factor_value,
                    "emission_factor_source": factor_source,
                    "emission_factor_version": factor_version,
                    "kg_co2e": kg_co2e,
                    "data_quality": item.data_quality,
                    "notes": item.notes,
                }
            )

        total = round(sum(stage_totals.values()), 3)
        confidence = {3: "measured", 2: "hybrid", 1: "estimated"}[confidence_floor]
        result = {
            "schema": "lca-calculation.v1",
            "product": {"id": product.id, "name": product.name, "category": product.category},
            "declared_unit": payload.declared_unit,
            "boundary": payload.boundary,
            "method_version": payload.method_version,
            "total_kg_co2e": total,
            "stage_totals": stage_totals,
            "confidence": confidence,
            "interpretation": self._interpret(product.category, total, payload.declared_unit),
        }
        calculation = LcaCalculation(
            organization_id=user.organization_id,
            product_id=product.id,
            created_by_user_id=user.id,
            declared_unit=payload.declared_unit,
            boundary=payload.boundary,
            method_version=payload.method_version,
            total_kg_co2e=total,
            confidence=confidence,
            inputs_json=calculated_inputs,
            stage_totals_json=stage_totals,
            result_json=result,
            notes=payload.notes,
        )
        self.db.add(calculation)
        self.db.flush()
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="lca_calculation",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
            metadata={"calculation_id": calculation.id, "total_kg_co2e": total},
        )
        self.db.commit()
        self.db.refresh(calculation)
        return calculation

    def list_calculations(self, user: User, product_id: str) -> LcaCalculationList:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        product = ProductRepository(self.db).get_for_org(user.organization_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        filters = [
            LcaCalculation.organization_id == user.organization_id,
            LcaCalculation.product_id == product_id,
        ]
        stmt = select(LcaCalculation).where(*filters).order_by(LcaCalculation.created_at.desc())
        count_stmt = select(func.count(LcaCalculation.id)).where(*filters)
        return LcaCalculationList(
            items=list(self.db.scalars(stmt)),
            total=int(self.db.scalar(count_stmt) or 0),
        )

    def _load_factors(self, organization_id: str, factor_ids: list[str]) -> dict[str, EmissionFactor]:
        if not factor_ids:
            return {}
        stmt = select(EmissionFactor).where(
            EmissionFactor.id.in_(factor_ids),
            or_(
                EmissionFactor.organization_id.is_(None),
                EmissionFactor.organization_id == organization_id,
            ),
        )
        factors = {factor.id: factor for factor in self.db.scalars(stmt)}
        missing = sorted(set(factor_ids) - set(factors.keys()))
        if missing:
            raise HTTPException(status_code=404, detail=f"Emission factor not found: {missing[0]}")
        return factors

    def _interpret(self, category: str, total: float, declared_unit: str) -> str:
        category_key = category.lower()
        if "cement" in category_key and "t" in declared_unit.lower():
            if total <= 500:
                return "Low-carbon range for cement benchmark screening."
            if total <= 750:
                return "Moderate cement footprint; verify clinker factor and supplementary cementitious materials."
            return "High cement footprint; prioritize clinker substitution, fuel switching, and energy efficiency review."
        if "concrete" in category_key:
            if total <= 250:
                return "Low-carbon concrete benchmark range."
            if total <= 400:
                return "Typical concrete footprint; optimize cement content and transport."
            return "High concrete footprint; review mix design, cement intensity, and A4 transport."
        return "Use this result as a screening estimate until verified against product category rules and supplier evidence."
