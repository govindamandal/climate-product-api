from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.product import EnvironmentalRecord, Product
from app.models.user import User

PRODUCTS = [
    ("Low-Carbon Concrete C35", "Concrete", 420, 1600, 720, 82),
    ("Portland Cement Blend LC3", "Cement", 780, 900, 980, 68),
    ("Recycled Structural Steel S355", "Steel", 1180, 520, 640, 91),
    ("Fired Clay Facade Brick", "Brick", 310, 740, 410, 74),
    ("Triple Glazed Unit", "Glass", 520, 680, 560, 79),
    ("Cross-Laminated Timber Panel", "Timber", 92, 410, 180, 95),
    ("Mineral Wool Insulation Board", "Insulation", 145, 350, 220, 88),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Organization).filter_by(slug="emidat-demo-manufacturing").first():
            return
        org = Organization(
            name="Emidat Demo Manufacturing",
            slug="emidat-demo-manufacturing",
            country="Germany",
        )
        db.add(org)
        db.flush()
        admin = User(
            organization_id=org.id,
            email="admin@emidat-demo.com",
            full_name="Mira Keller",
            role=UserRole.ORG_ADMIN,
            hashed_password=hash_password("ClimatePass123!"),
        )
        db.add(admin)
        db.flush()
        for name, category, co2, water, energy, score in PRODUCTS:
            product = Product(
                organization_id=org.id,
                name=name,
                category=category,
                description="Commercial building material used in European construction projects.",
                manufacturer="Emidat Demo Manufacturing",
                country="Germany",
                production_method="Verified batch production with supplier traceability",
                material_composition={"primary": category, "recycled_content_pct": max(score - 55, 5)},
                certifications=[{"name": "EPD EN 15804", "status": "verified"}],
            )
            db.add(product)
            db.flush()
            db.add(
                EnvironmentalRecord(
                    organization_id=org.id,
                    product_id=product.id,
                    co2_kg=co2,
                    water_liters=water,
                    energy_kwh=energy,
                    transportation_kg_co2=round(co2 * 0.16, 1),
                    recyclability_score=min(score + 3, 100),
                    sustainability_score=score,
                    notes="Seeded benchmark-ready LCA record.",
                )
            )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
