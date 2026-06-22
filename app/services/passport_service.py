from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.product import PassportRead
from app.services.product_service import ProductService


class PassportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate(self, user: User, product_id: str) -> PassportRead:
        product = ProductService(self.db).get_product(user, product_id)
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
            },
            "material_composition": product.material_composition,
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
