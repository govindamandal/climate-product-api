from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client: TestClient, slug: str, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": slug.replace("-", " ").title(),
            "organization_slug": slug,
            "country": "Germany",
            "full_name": "Test Admin",
            "email": email,
            "password": "ClimatePass123!",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_auth_preflight_allows_web_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_registration_login_and_product_lifecycle(client: TestClient) -> None:
    auth = register(client, "tenant-alpha", "admin@alpha.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Low Carbon Concrete",
            "category": "Concrete",
            "description": "Concrete with reduced clinker intensity.",
            "manufacturer": "Alpha Materials",
            "country": "Germany",
            "production_method": "Batch plant",
            "image_url": "https://assets.example.com/products/concrete.jpg",
            "material_composition": {"cement": 18, "aggregate": 72, "additives": 10},
            "certifications": [{"name": "EPD EN 15804"}],
            "environmental_record": {
                "co2_kg": 410,
                "water_liters": 1500,
                "energy_kwh": 650,
                "transportation_kg_co2": 55,
                "recyclability_score": 82,
                "sustainability_score": 84,
            },
        },
    )
    assert created.status_code == 201, created.text

    listed = client.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["image_url"] == "https://assets.example.com/products/concrete.jpg"
    assert listed.json()["items"][0]["environmental_records"][0]["co2_kg"] == 410

    image_upload = client.post(
        f"/api/v1/products/{listed.json()['items'][0]['id']}/image",
        headers=headers,
        files={"file": ("product.png", b"fake-image", "image/png")},
    )
    assert image_upload.status_code == 503
    assert image_upload.json()["detail"] == "Cloudflare R2 storage is not configured"


def test_tenant_isolation(client: TestClient) -> None:
    alpha = register(client, "tenant-alpha", "admin@alpha.example")
    beta = register(client, "tenant-beta", "admin@beta.example")
    alpha_headers = {"Authorization": f"Bearer {alpha['access_token']}"}
    beta_headers = {"Authorization": f"Bearer {beta['access_token']}"}

    product = client.post(
        "/api/v1/products",
        headers=alpha_headers,
        json={
            "name": "Private Steel",
            "category": "Steel",
            "description": "",
            "manufacturer": "Alpha",
            "country": "Germany",
            "production_method": "Electric arc furnace",
        },
    ).json()

    forbidden_lookup = client.get(f"/api/v1/products/{product['id']}", headers=beta_headers)
    assert forbidden_lookup.status_code == 404
    beta_list = client.get("/api/v1/products", headers=beta_headers)
    assert beta_list.json()["total"] == 0


def test_csv_import_filtering_and_delete(client: TestClient) -> None:
    auth = register(client, "tenant-import", "admin@import.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    csv_content = "\n".join(
        [
            "name,category,description,manufacturer,country,production_method,co2_kg,water_liters,energy_kwh,transportation_kg_co2,recyclability_score,sustainability_score,recycled_content_pct,certification_name",
            "Circular Brick,Brick,Low waste brick,Import Materials,Germany,Kiln optimized,220,650,330,31,78,81,22,EPD EN 15804",
            "Bio Insulation,Insulation,Fiber board,Import Materials,France,Press cured,120,310,180,18,92,89,64,FSC Mix",
        ]
    )

    imported = client.post(
        "/api/v1/products/imports/csv",
        headers=headers,
        files={"file": ("products.csv", csv_content, "text/csv")},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["created"] == 2

    brick_list = client.get("/api/v1/products?category=Brick&page_size=1", headers=headers)
    assert brick_list.status_code == 200
    assert brick_list.json()["total"] == 1
    assert brick_list.json()["categories"] == ["Brick", "Insulation"]
    brick = brick_list.json()["items"][0]
    assert brick["environmental_records"][0]["sustainability_score"] == 81

    deleted = client.delete(f"/api/v1/products/{brick['id']}", headers=headers)
    assert deleted.status_code == 204
    after_delete = client.get("/api/v1/products?category=Brick", headers=headers)
    assert after_delete.json()["total"] == 0


def test_sustainability_analytics_summary(client: TestClient) -> None:
    auth = register(client, "tenant-analytics", "admin@analytics.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    for name, category, co2, score in [
        ("Analytics Concrete", "Concrete", 500, 72),
        ("Analytics Timber", "Timber", 80, 94),
    ]:
        response = client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": name,
                "category": category,
                "description": "",
                "manufacturer": "Analytics Materials",
                "country": "Germany",
                "production_method": "Verified production",
                "environmental_record": {
                    "co2_kg": co2,
                    "water_liters": 100,
                    "energy_kwh": 200,
                    "transportation_kg_co2": 20,
                    "recyclability_score": 80,
                    "sustainability_score": score,
                },
            },
        )
        assert response.status_code == 201, response.text

    summary = client.get("/api/v1/analytics/summary", headers=headers)
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["product_count"] == 2
    assert payload["measured_product_count"] == 2
    assert payload["total_co2"] == 580
    assert payload["average_sustainability_score"] == 83
    assert payload["category_breakdown"][0]["category"] == "Concrete"
    assert payload["hotspots"][0]["name"] == "Analytics Concrete"
    assert payload["score_distribution"][-1]["count"] == 1
