from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import AuditAction
from app.models.passport_share import PassportShare
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.product import PassportRead, PassportShareRead, PublicPassportRead
from app.services.audit_service import AuditService
from app.services.product_service import ProductService


class PassportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate(self, user: User, product_id: str) -> PassportRead:
        product = ProductService(self.db).get_product(user, product_id)
        return self._passport_for_product(product)

    def create_share(self, user: User, product_id: str) -> PassportShareRead:
        product = ProductService(self.db).get_product(user, product_id)
        share = self.db.scalar(
            select(PassportShare).where(
                PassportShare.organization_id == product.organization_id,
                PassportShare.product_id == product.id,
                PassportShare.is_active.is_(True),
            )
        )
        if not share:
            share = PassportShare(
                organization_id=product.organization_id,
                product_id=product.id,
                created_by_user_id=user.id,
                token=token_urlsafe(32),
            )
            self.db.add(share)
            self.db.flush()
            AuditService(self.db).record(
                action=AuditAction.EXPORT,
                entity_type="passport_share",
                organization_id=product.organization_id,
                actor_user_id=user.id,
                entity_id=product.id,
                metadata={"product_name": product.name},
            )
            self.db.commit()
            self.db.refresh(share)
        return self._share_read(share)

    def public_passport(self, token: str) -> PublicPassportRead:
        share = self.db.scalar(
            select(PassportShare).where(PassportShare.token == token, PassportShare.is_active.is_(True))
        )
        if not share:
            raise HTTPException(status_code=404, detail="Public passport not found")
        product = ProductRepository(self.db).get_for_org(share.organization_id, share.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Public passport not found")
        passport = self._passport_for_product(product)
        return PublicPassportRead(
            product=passport.product,
            latest_environmental_record=passport.latest_environmental_record,
            sustainability_score=passport.sustainability_score,
            passport_json=passport.passport_json,
            share=self._share_read(share),
        )

    def _passport_for_product(self, product) -> PassportRead:
        latest = product.environmental_records[0] if product.environmental_records else None
        score = latest.sustainability_score if latest else 0
        passport = {
            "schema": "digital-product-passport.v1",
            "product": {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "manufacturer": product.manufacturer,
                "country": product.country,
                "production_method": product.production_method,
                "product_code": product.product_code,
                "declared_unit": product.declared_unit,
                "functional_unit": product.functional_unit,
                "lifecycle_scope": product.lifecycle_scope,
                "reference_service_life_years": product.reference_service_life_years,
                "manufacturing_site": product.manufacturing_site,
                "plant_code": product.plant_code,
                "product_standard": product.product_standard,
                "pcr": product.pcr,
                "geography": product.geography,
                "data_quality": product.data_quality,
                "technical_properties": product.technical_properties,
            },
            "material_composition": product.material_composition,
            "material_components": [
                {
                    "material_name": component.material_name,
                    "category": component.category,
                    "percentage": component.percentage,
                    "recycled_content_pct": component.recycled_content_pct,
                    "bio_based_content_pct": component.bio_based_content_pct,
                    "supplier": component.supplier,
                    "origin_country": component.origin_country,
                    "evidence_reference": component.evidence_reference,
                }
                for component in product.material_components
            ],
            "certifications": product.certifications,
            "environmental_metrics": latest.model_dump() if hasattr(latest, "model_dump") else None,
            "sustainability_score": score,
        }
        if latest:
            passport["environmental_metrics"] = {
                "co2_kg": latest.co2_kg,
                "water_liters": latest.water_liters,
                "energy_kwh": latest.energy_kwh,
                "transportation_kg_co2": latest.transportation_kg_co2,
                "recyclability_score": latest.recyclability_score,
            }
        return PassportRead(
            product=product,
            latest_environmental_record=latest,
            sustainability_score=score,
            passport_json=passport,
        )

    def _share_read(self, share: PassportShare) -> PassportShareRead:
        return PassportShareRead(
            id=share.id,
            product_id=share.product_id,
            token=share.token,
            share_url=f"{get_settings().frontend_base_url.rstrip('/')}/share/passports/{share.token}",
            is_active=share.is_active,
            created_at=share.created_at,
        )
