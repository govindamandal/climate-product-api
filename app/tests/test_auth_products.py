from collections.abc import Generator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import Settings
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.lca import EmissionFactor
from app.models.user import User
from app.services.ai_service import LocalAIProvider, build_ai_provider
from app.services.email_service import EmailService


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
    app.state.TestingSessionLocal = TestingSessionLocal
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


def create_super_admin(client: TestClient) -> dict:
    db = client.app.state.TestingSessionLocal()
    try:
        user = User(
            organization_id=None,
            email="superadmin@example.com",
            full_name="Platform Admin",
            role=UserRole.SUPER_ADMIN,
            hashed_password=hash_password("ClimatePass123!"),
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@example.com", "password": "ClimatePass123!"},
    )
    assert response.status_code == 200, response.text
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


def test_database_url_normalizes_postgres_driver() -> None:
    settings = Settings(database_url="postgres://user:pass@example.com/db")

    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_database_url_strips_query_value_whitespace() -> None:
    settings = Settings(
        database_url="postgres://user:pass@example.com/db?sslmode=require&channel_binding=require\n"
    )

    assert settings.sqlalchemy_database_url.endswith("sslmode=require&channel_binding=require")
    assert "require%0A" not in settings.sqlalchemy_database_url


def test_health_includes_trace_headers(client: TestClient) -> None:
    response = client.get("/health", headers={"x-request-id": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"
    assert float(response.headers["x-process-time-ms"]) >= 0


def test_readiness_reports_dependency_checks(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Climate Product Platform API"
    assert payload["status"] in {"ok", "degraded"}
    assert payload["uptime_seconds"] >= 0
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["database"]["status"] == "ok"
    assert checks["database"]["latency_ms"] is not None
    assert checks["cache"]["status"] in {"ok", "degraded"}


def test_security_headers_are_applied(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_large_request_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(11 * 1024 * 1024),
        },
    )

    assert response.status_code == 413


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
            "product_code": "LCC-C35",
            "declared_unit": "1 m3",
            "functional_unit": "One cubic metre of structural concrete.",
            "lifecycle_scope": "cradle-to-gate",
            "manufacturing_site": "Berlin Plant",
            "plant_code": "BER-01",
            "product_standard": "EN 206",
            "pcr": "Construction products PCR",
            "geography": "Germany",
            "data_quality": "measured",
            "technical_properties": {"compressive_strength_mpa": 35},
            "image_url": "https://assets.example.com/products/concrete.jpg",
            "material_composition": {"cement": 18, "aggregate": 72, "additives": 10},
            "material_components": [
                {
                    "material_name": "CEM II cement",
                    "category": "Cement",
                    "percentage": 18,
                    "recycled_content_pct": 0,
                    "supplier": "Alpha Cement Works",
                    "origin_country": "Germany",
                    "evidence_reference": "Supplier declaration 2026",
                },
                {
                    "material_name": "Recycled aggregate",
                    "category": "Aggregate",
                    "percentage": 72,
                    "recycled_content_pct": 40,
                    "origin_country": "Germany",
                },
            ],
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
    assert listed.json()["items"][0]["declared_unit"] == "1 m3"
    assert listed.json()["items"][0]["technical_properties"]["compressive_strength_mpa"] == 35
    assert listed.json()["items"][0]["material_components"][0]["material_name"] == "CEM II cement"

    detail = client.get(f"/api/v1/products/{listed.json()['items'][0]['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["product_standard"] == "EN 206"
    assert len(detail.json()["material_components"]) == 2

    image_upload = client.post(
        f"/api/v1/products/{listed.json()['items'][0]['id']}/image",
        headers=headers,
        files={"file": ("product.png", b"fake-image", "image/png")},
    )
    assert image_upload.status_code == 503
    assert image_upload.json()["detail"] == "Cloudflare R2 storage is not configured"


def test_dpp_public_sharing_is_tokenized_and_tenant_scoped(client: TestClient) -> None:
    auth = register(client, "tenant-dpp-share", "admin@dpp-share.example")
    other = register(client, "tenant-dpp-other", "admin@dpp-other.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Public DPP Panel",
            "category": "Facade",
            "description": "Shareable product passport.",
            "manufacturer": "DPP Materials",
            "country": "Germany",
            "production_method": "Precast",
            "material_composition": {"cement": 30, "aggregate": 60},
            "certifications": [{"name": "EPD EN 15804"}],
            "environmental_record": {
                "co2_kg": 300,
                "water_liters": 700,
                "energy_kwh": 390,
                "transportation_kg_co2": 28,
                "recyclability_score": 80,
                "sustainability_score": 86,
            },
        },
    )
    product_id = created.json()["id"]

    share = client.post(f"/api/v1/passports/{product_id}/shares", headers=headers)

    assert share.status_code == 201, share.text
    assert "/share/passports/" in share.json()["share_url"]
    blocked = client.post(f"/api/v1/passports/{product_id}/shares", headers=other_headers)
    assert blocked.status_code == 404

    public = client.get(f"/api/v1/passports/public/{share.json()['token']}")
    assert public.status_code == 200
    assert public.json()["product"]["name"] == "Public DPP Panel"
    assert public.json()["sustainability_score"] == 86
    assert public.json()["share"]["token"] == share.json()["token"]


def test_password_reset_updates_password_and_revokes_refresh_tokens(client: TestClient) -> None:
    auth = register(client, "tenant-reset", "admin@reset.example")

    requested = client.post(
        "/api/v1/auth/forgot-password",
        json={"organization_slug": "tenant-reset", "email": "admin@reset.example"},
    )
    assert requested.status_code == 202, requested.text
    reset_url = requested.json()["reset_url"]
    token = parse_qs(urlparse(reset_url).query)["token"][0]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "NewClimatePass123!"},
    )
    assert reset.status_code == 200, reset.text

    old_login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-reset",
            "email": "admin@reset.example",
            "password": "ClimatePass123!",
        },
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-reset",
            "email": "admin@reset.example",
            "password": "NewClimatePass123!",
        },
    )
    assert new_login.status_code == 200

    revoked_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth["refresh_token"]},
    )
    assert revoked_refresh.status_code == 401

    reused_token = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "AnotherClimatePass123!"},
    )
    assert reused_token.status_code == 400

    invite_with_reset_token = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "InviteClimatePass123!"},
    )
    assert invite_with_reset_token.status_code == 400


def test_password_reset_sends_email(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    register(client, "tenant-reset-email", "admin@reset-email.example")
    sent: list[dict] = []

    def fake_send_password_reset(self, **kwargs) -> bool:
        sent.append(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_password_reset", fake_send_password_reset)

    requested = client.post(
        "/api/v1/auth/forgot-password",
        json={"organization_slug": "tenant-reset-email", "email": "admin@reset-email.example"},
    )

    assert requested.status_code == 202
    assert sent[0]["to_email"] == "admin@reset-email.example"
    assert "/reset-password?token=" in sent[0]["reset_url"]


def test_password_reset_requires_tenant_context_for_duplicate_email(client: TestClient) -> None:
    register(client, "tenant-reset-alpha", "shared@example.com")
    register(client, "tenant-reset-beta", "shared@example.com")

    ambiguous = client.post("/api/v1/auth/forgot-password", json={"email": "shared@example.com"})
    assert ambiguous.status_code == 202
    assert ambiguous.json()["reset_url"] is None

    scoped = client.post(
        "/api/v1/auth/forgot-password",
        json={"organization_slug": "tenant-reset-beta", "email": "shared@example.com"},
    )
    assert scoped.status_code == 202
    assert scoped.json()["reset_url"]


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


def test_organization_team_management_and_audit_logs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = register(client, "tenant-team", "admin@team.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    sent_invites: list[dict] = []

    def fake_send_invite(self, **kwargs) -> bool:
        sent_invites.append(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_invite", fake_send_invite)

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=headers,
        json={
            "email": "manager@team.example",
            "full_name": "Sustainability Manager",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text
    assert sent_invites[0]["to_email"] == "manager@team.example"
    assert sent_invites[0]["organization_name"] == "Tenant Team"
    assert "/accept-invite?token=" in sent_invites[0]["invite_url"]
    members = invited.json()["members"]
    member = next(item for item in members if item["email"] == "manager@team.example")
    assert member["role"] == "org_user"

    updated = client.patch(
        f"/api/v1/organizations/team/{member['id']}",
        headers=headers,
        json={"role": "org_admin", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["role"] == "org_admin"
    assert updated.json()["is_active"] is False

    audit_logs = client.get("/api/v1/organizations/audit-logs", headers=headers)
    assert audit_logs.status_code == 200, audit_logs.text
    assert audit_logs.json()["total"] >= 3
    assert {item["entity_type"] for item in audit_logs.json()["items"]} >= {
        "organization",
        "user_invite",
        "team_member",
    }
    assert any(item["actor_email"] == "admin@team.example" for item in audit_logs.json()["items"])
    assert any(item["description"] for item in audit_logs.json()["items"])

    filtered_logs = client.get(
        "/api/v1/organizations/audit-logs?entity_type=team_member&search=admin@team.example",
        headers=headers,
    )
    assert filtered_logs.status_code == 200
    assert filtered_logs.json()["total"] == 1
    assert filtered_logs.json()["items"][0]["entity_type"] == "team_member"

    self_update = client.patch(
        f"/api/v1/organizations/team/{auth['user']['id']}",
        headers=headers,
        json={"role": "org_user"},
    )
    assert self_update.status_code == 400

    removed = client.delete(f"/api/v1/organizations/team/{member['id']}", headers=headers)
    assert removed.status_code == 204
    team = client.get("/api/v1/organizations/team", headers=headers)
    assert all(item["email"] != "manager@team.example" for item in team.json()["members"])


def test_invited_user_accepts_invite_and_receives_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = register(client, "tenant-invite-accept", "admin@invite-accept.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    sent_invites: list[dict] = []

    def fake_send_invite(self, **kwargs) -> bool:
        sent_invites.append(kwargs)
        return True

    monkeypatch.setattr(EmailService, "send_invite", fake_send_invite)
    invited = client.post(
        "/api/v1/organizations/invites",
        headers=headers,
        json={
            "email": "new.member@invite-accept.example",
            "full_name": "New Member",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text
    invite_token = parse_qs(urlparse(sent_invites[0]["invite_url"]).query)["token"][0]

    accepted = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite_token, "password": "AcceptedClimatePass123!"},
    )
    assert accepted.status_code == 200, accepted.text
    session = accepted.json()
    assert session["user"]["email"] == "new.member@invite-accept.example"
    assert session["user"]["role"] == "org_user"
    assert session["access_token"]

    reused = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite_token, "password": "AcceptedClimatePass123!"},
    )
    assert reused.status_code == 400


def test_organization_team_management_is_tenant_scoped(client: TestClient) -> None:
    alpha = register(client, "tenant-team-alpha", "admin@team-alpha.example")
    beta = register(client, "tenant-team-beta", "admin@team-beta.example")
    alpha_headers = {"Authorization": f"Bearer {alpha['access_token']}"}
    beta_headers = {"Authorization": f"Bearer {beta['access_token']}"}

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=alpha_headers,
        json={
            "email": "member@team-alpha.example",
            "full_name": "Alpha Member",
            "role": "org_user",
        },
    )
    member = next(item for item in invited.json()["members"] if item["email"] == "member@team-alpha.example")

    forbidden_update = client.patch(
        f"/api/v1/organizations/team/{member['id']}",
        headers=beta_headers,
        json={"role": "org_admin"},
    )
    assert forbidden_update.status_code == 404

    beta_team = client.get("/api/v1/organizations/team", headers=beta_headers)
    assert beta_team.status_code == 200
    assert beta_team.json()["organization"]["slug"] == "tenant-team-beta"
    assert all(item["email"] != "member@team-alpha.example" for item in beta_team.json()["members"])


def test_privacy_controls_and_data_requests_are_tenant_scoped(client: TestClient) -> None:
    alpha = register(client, "tenant-privacy-alpha", "admin@privacy-alpha.example")
    beta = register(client, "tenant-privacy-beta", "admin@privacy-beta.example")
    alpha_headers = {"Authorization": f"Bearer {alpha['access_token']}"}
    beta_headers = {"Authorization": f"Bearer {beta['access_token']}"}

    defaults = client.get("/api/v1/organizations/privacy-settings", headers=alpha_headers)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["data_region"] == "India"
    assert defaults.json()["allow_ai_processing"] is True

    updated = client.patch(
        "/api/v1/organizations/privacy-settings",
        headers=alpha_headers,
        json={
            "data_region": "India - Mumbai",
            "retention_period_days": 1095,
            "allow_ai_processing": False,
            "require_verification_for_exports": True,
            "data_processing_contact_email": "privacy@alpha.example",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data_region"] == "India - Mumbai"
    assert updated.json()["allow_ai_processing"] is False

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=alpha_headers,
        json={
            "email": "member@privacy-alpha.example",
            "full_name": "Privacy Contributor",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-privacy-alpha",
            "email": "member@privacy-alpha.example",
            "password": "ChangeMeNow!2026",
        },
    )
    assert login.status_code == 200, login.text
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    blocked_settings_update = client.patch(
        "/api/v1/organizations/privacy-settings",
        headers=user_headers,
        json={"allow_ai_processing": True},
    )
    assert blocked_settings_update.status_code == 403

    created_request = client.post(
        "/api/v1/organizations/data-requests",
        headers=user_headers,
        json={
            "request_type": "export",
            "subject_type": "organization",
            "reason": "Prepare a buyer diligence export.",
        },
    )
    assert created_request.status_code == 201, created_request.text
    request_id = created_request.json()["id"]
    assert created_request.json()["requested_by_email"] == "member@privacy-alpha.example"

    beta_requests = client.get("/api/v1/organizations/data-requests", headers=beta_headers)
    assert beta_requests.status_code == 200
    assert beta_requests.json()["total"] == 0

    tenant_blocked_review = client.patch(
        f"/api/v1/organizations/data-requests/{request_id}",
        headers=beta_headers,
        json={"status": "completed", "resolution_notes": "Wrong tenant."},
    )
    assert tenant_blocked_review.status_code == 404

    user_blocked_review = client.patch(
        f"/api/v1/organizations/data-requests/{request_id}",
        headers=user_headers,
        json={"status": "completed", "resolution_notes": "Done."},
    )
    assert user_blocked_review.status_code == 403

    completed = client.patch(
        f"/api/v1/organizations/data-requests/{request_id}",
        headers=alpha_headers,
        json={"status": "completed", "resolution_notes": "Export prepared and shared internally."},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["reviewed_by_email"] == "admin@privacy-alpha.example"

    audit_logs = client.get(
        "/api/v1/organizations/audit-logs?entity_type=data_governance_request",
        headers=alpha_headers,
    )
    assert audit_logs.status_code == 200
    assert audit_logs.json()["total"] >= 2


def test_billing_summary_and_plan_changes_are_tenant_scoped(client: TestClient) -> None:
    auth = register(client, "tenant-billing", "admin@billing.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    plans = client.get("/api/v1/billing/plans", headers=headers)
    assert plans.status_code == 200, plans.text
    assert {plan["key"] for plan in plans.json()} >= {"starter", "growth", "enterprise"}

    summary = client.get("/api/v1/billing/current", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["subscription"]["plan_key"] == "starter"
    assert summary.json()["usage"]["users"] == 1
    assert summary.json()["usage"]["products"] == 0

    upgraded = client.patch(
        "/api/v1/billing/current",
        headers=headers,
        json={"plan_key": "growth", "billing_cycle": "annual"},
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["subscription"]["plan_key"] == "growth"
    assert upgraded.json()["subscription"]["billing_cycle"] == "annual"
    assert upgraded.json()["subscription"]["status"] == "active"
    assert upgraded.json()["usage"]["seats_included"] == 10

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=headers,
        json={
            "email": "member@billing.example",
            "full_name": "Billing Member",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-billing",
            "email": "member@billing.example",
            "password": "ChangeMeNow!2026",
        },
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    user_summary = client.get("/api/v1/billing/current", headers=user_headers)
    assert user_summary.status_code == 200
    blocked = client.patch(
        "/api/v1/billing/current",
        headers=user_headers,
        json={"plan_key": "enterprise", "billing_cycle": "annual"},
    )
    assert blocked.status_code == 403

    audit_logs = client.get(
        "/api/v1/organizations/audit-logs?entity_type=billing_subscription",
        headers=headers,
    )
    assert audit_logs.status_code == 200
    assert audit_logs.json()["total"] == 1


def test_org_user_permissions_allow_contribution_but_block_admin_actions(client: TestClient) -> None:
    auth = register(client, "tenant-rbac", "admin@rbac.example")
    admin_headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=admin_headers,
        json={
            "name": "RBAC Facade Panel",
            "category": "Facade",
            "description": "Permission scoped product.",
            "manufacturer": "RBAC Materials",
            "country": "Germany",
            "production_method": "Precast",
        },
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=admin_headers,
        json={
            "email": "contributor@rbac.example",
            "full_name": "Product Contributor",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text

    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-rbac",
            "email": "contributor@rbac.example",
            "password": "ChangeMeNow!2026",
        },
    )
    assert login.status_code == 200, login.text
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    updated = client.patch(
        f"/api/v1/products/{product_id}",
        headers=user_headers,
        json={"description": "Contributor updated the product description."},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Contributor updated the product description."

    for method, path in [
        ("delete", f"/api/v1/products/{product_id}"),
        ("post", f"/api/v1/passports/{product_id}/shares"),
        ("post", "/api/v1/organizations/invites"),
        ("get", "/api/v1/organizations/audit-logs"),
    ]:
        request = getattr(client, method)
        response = (
            request(path, headers=user_headers, json={})
            if method == "post"
            else request(path, headers=user_headers)
        )
        assert response.status_code == 403, response.text


def test_product_verification_workflow_is_reviewed_by_org_admin(client: TestClient) -> None:
    auth = register(client, "tenant-verification", "admin@verification.example")
    admin_headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=admin_headers,
        json={
            "name": "Verified Facade Panel",
            "category": "Facade",
            "description": "Panel ready for evidence review.",
            "manufacturer": "Verification Materials",
            "country": "Germany",
            "production_method": "Precast",
        },
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    invited = client.post(
        "/api/v1/organizations/invites",
        headers=admin_headers,
        json={
            "email": "submitter@verification.example",
            "full_name": "Verification Submitter",
            "role": "org_user",
        },
    )
    assert invited.status_code == 200, invited.text
    login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "tenant-verification",
            "email": "submitter@verification.example",
            "password": "ChangeMeNow!2026",
        },
    )
    assert login.status_code == 200, login.text
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    submitted = client.post(
        "/api/v1/verifications",
        headers=user_headers,
        json={
            "product_id": product_id,
            "verification_type": "internal_review",
            "scope": "product_dpp",
            "evidence_summary": "DPP metadata, certificate, and latest environmental record attached.",
            "requester_notes": "Please review before sharing with buyers.",
        },
    )
    assert submitted.status_code == 201, submitted.text
    verification_id = submitted.json()["id"]
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["product_name"] == "Verified Facade Panel"

    duplicate = client.post(
        "/api/v1/verifications",
        headers=user_headers,
        json={"product_id": product_id},
    )
    assert duplicate.status_code == 409

    user_review = client.patch(
        f"/api/v1/verifications/{verification_id}/review",
        headers=user_headers,
        json={"status": "approved", "reviewer_notes": "Looks good."},
    )
    assert user_review.status_code == 403

    approved = client.patch(
        f"/api/v1/verifications/{verification_id}/review",
        headers=admin_headers,
        json={"status": "approved", "reviewer_notes": "Evidence is sufficient for buyer DPP use."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by_email"] == "admin@verification.example"

    listed = client.get("/api/v1/verifications?status=approved", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == verification_id

    audit_logs = client.get("/api/v1/organizations/audit-logs?entity_type=product_verification", headers=admin_headers)
    assert audit_logs.status_code == 200
    assert audit_logs.json()["total"] >= 2


def test_product_verification_requests_are_tenant_scoped(client: TestClient) -> None:
    alpha = register(client, "tenant-verification-alpha", "admin@verification-alpha.example")
    beta = register(client, "tenant-verification-beta", "admin@verification-beta.example")
    alpha_headers = {"Authorization": f"Bearer {alpha['access_token']}"}
    beta_headers = {"Authorization": f"Bearer {beta['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=alpha_headers,
        json={
            "name": "Tenant Scoped Panel",
            "category": "Facade",
            "description": "Tenant scoped verification product.",
            "manufacturer": "Alpha Materials",
            "country": "Germany",
            "production_method": "Precast",
        },
    )
    product_id = created.json()["id"]

    blocked = client.post("/api/v1/verifications", headers=beta_headers, json={"product_id": product_id})

    assert blocked.status_code == 404


def test_super_admin_platform_management(client: TestClient) -> None:
    super_auth = create_super_admin(client)
    headers = {"Authorization": f"Bearer {super_auth['access_token']}"}

    created = client.post(
        "/api/v1/platform/organizations",
        headers=headers,
        json={
            "name": "Platform Concrete Co",
            "slug": "platform-concrete",
            "country": "Germany",
            "admin_email": "admin@platform-concrete.example",
            "admin_full_name": "Platform Tenant Admin",
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["temporary_password"] == "ChangeMeNow!2026"
    assert payload["organization"]["slug"] == "platform-concrete"
    assert payload["organization"]["user_count"] == 1

    organizations = client.get("/api/v1/platform/organizations", headers=headers)
    assert organizations.status_code == 200
    assert organizations.json()["total"] == 1

    updated = client.patch(
        f"/api/v1/platform/organizations/{payload['organization']['id']}",
        headers=headers,
        json={"subscription_status": "active"},
    )
    assert updated.status_code == 200
    assert updated.json()["subscription_status"] == "active"

    tenant_login = client.post(
        "/api/v1/auth/login",
        json={
            "organization_slug": "platform-concrete",
            "email": "admin@platform-concrete.example",
            "password": "ChangeMeNow!2026",
        },
    )
    tenant_headers = {"Authorization": f"Bearer {tenant_login.json()['access_token']}"}
    billing = client.patch(
        "/api/v1/billing/current",
        headers=tenant_headers,
        json={"plan_key": "growth", "billing_cycle": "monthly"},
    )
    assert billing.status_code == 200, billing.text

    organizations_after_billing = client.get("/api/v1/platform/organizations", headers=headers)
    assert organizations_after_billing.status_code == 200
    assert organizations_after_billing.json()["items"][0]["billing_plan_key"] == "growth"
    assert organizations_after_billing.json()["items"][0]["billing_cycle"] == "monthly"

    analytics = client.get("/api/v1/platform/analytics", headers=headers)
    assert analytics.status_code == 200
    assert analytics.json()["organization_count"] == 1
    assert analytics.json()["active_subscription_count"] == 1

    users = client.get("/api/v1/platform/users", headers=headers)
    assert users.status_code == 200
    assert users.json()["total"] == 2

    audit_logs = client.get("/api/v1/platform/audit-logs", headers=headers)
    assert audit_logs.status_code == 200
    assert audit_logs.json()["total"] >= 2
    assert any(item["organization_name"] == "Platform Concrete Co" for item in audit_logs.json()["items"])

    filtered_logs = client.get(
        "/api/v1/platform/audit-logs?action=update&entity_type=subscription&search=Platform",
        headers=headers,
    )
    assert filtered_logs.status_code == 200
    assert filtered_logs.json()["total"] == 1
    assert filtered_logs.json()["items"][0]["entity_type"] == "subscription"


def test_platform_routes_require_super_admin(client: TestClient) -> None:
    auth = register(client, "tenant-not-platform", "admin@not-platform.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    response = client.get("/api/v1/platform/analytics", headers=headers)
    assert response.status_code == 403

    operations = client.get("/api/v1/operations/status", headers=headers)
    assert operations.status_code == 403


def test_super_admin_can_view_operations_status(client: TestClient) -> None:
    super_auth = create_super_admin(client)
    headers = {"Authorization": f"Bearer {super_auth['access_token']}"}

    response = client.get("/api/v1/operations/status", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["environment"] == "local"
    assert payload["status"] in {"ok", "degraded"}
    assert {check["name"] for check in payload["checks"]} == {"database", "cache"}


def test_ai_provider_defaults_to_local_without_remote_credentials() -> None:
    provider = build_ai_provider(Settings(ai_provider="openai", openai_api_key=None))

    assert isinstance(provider, LocalAIProvider)
    assert provider.name == "local"


def test_ai_advisor_and_report_use_configured_provider_contract(client: TestClient) -> None:
    auth = register(client, "tenant-ai", "admin@ai.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "AI Concrete",
            "category": "Concrete",
            "description": "Concrete with measured impacts.",
            "manufacturer": "AI Materials",
            "country": "Germany",
            "production_method": "Batch plant",
            "environmental_record": {
                "co2_kg": 500,
                "water_liters": 1200,
                "energy_kwh": 650,
                "transportation_kg_co2": 110,
                "recyclability_score": 60,
                "sustainability_score": 70,
            },
        },
    )
    product_id = created.json()["id"]

    advisor = client.post(f"/api/v1/ai/products/{product_id}/advisor", headers=headers)
    report = client.post(f"/api/v1/ai/products/{product_id}/report", headers=headers)

    assert advisor.status_code == 200
    assert advisor.json()["provider"] == "local"
    assert advisor.json()["safety"]["status"] == "validated"
    assert advisor.json()["safety"]["execution_mode"] == "deterministic"
    assert advisor.json()["recommendations"]
    assert report.status_code == 200
    assert report.json()["provider"] == "local"
    assert report.json()["safety"]["disclaimers"]
    assert "AI Concrete" in report.json()["summary"]
    assert "AI Safety Notes" in report.json()["markdown"]


def test_ai_jobs_create_and_store_results(client: TestClient) -> None:
    auth = register(client, "tenant-ai-jobs", "admin@ai-jobs.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Async AI Concrete",
            "category": "Concrete",
            "description": "Concrete with async AI workflows.",
            "manufacturer": "AI Materials",
            "country": "Germany",
            "production_method": "Batch plant",
            "environmental_record": {
                "co2_kg": 500,
                "water_liters": 1200,
                "energy_kwh": 650,
                "transportation_kg_co2": 110,
                "recyclability_score": 60,
                "sustainability_score": 70,
            },
        },
    )
    product_id = created.json()["id"]

    queued = client.post(f"/api/v1/ai/products/{product_id}/report/jobs", headers=headers)

    assert queued.status_code == 202, queued.text
    assert queued.json()["job_type"] == "report"
    job = client.get(f"/api/v1/ai/jobs/{queued.json()['id']}", headers=headers)
    assert job.status_code == 200
    assert job.json()["status"] == "succeeded"
    assert job.json()["provider"] == "local"
    assert job.json()["safety_status"] == "validated"
    assert job.json()["safety_metadata_json"]["policy_version"] == "ai-safety.v1"
    assert "Async AI Concrete" in job.json()["result_json"]["summary"]


def test_ai_processing_respects_organization_privacy_setting(client: TestClient) -> None:
    auth = register(client, "tenant-ai-policy", "admin@ai-policy.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Policy Concrete",
            "category": "Concrete",
            "description": "Concrete used to test AI privacy controls.",
            "manufacturer": "Policy Materials",
            "country": "Germany",
            "production_method": "Batch plant",
        },
    )
    product_id = created.json()["id"]
    disabled = client.patch(
        "/api/v1/organizations/privacy-settings",
        headers=headers,
        json={"allow_ai_processing": False},
    )
    assert disabled.status_code == 200, disabled.text

    advisor = client.post(f"/api/v1/ai/products/{product_id}/advisor", headers=headers)
    queued = client.post(f"/api/v1/ai/products/{product_id}/advisor/jobs", headers=headers)

    assert advisor.status_code == 403
    assert advisor.json()["detail"] == "AI processing is disabled for this organization"
    assert queued.status_code == 403


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


def test_product_benchmarks_include_category_context(client: TestClient) -> None:
    auth = register(client, "tenant-benchmarks", "admin@benchmarks.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    for name, category, co2, water, energy, score in [
        ("Standard Concrete", "Concrete", 600, 1500, 700, 62),
        ("Low Carbon Concrete", "Concrete", 360, 1200, 420, 84),
        ("Circular Brick", "Brick", 220, 650, 330, 81),
    ]:
        response = client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": name,
                "category": category,
                "description": "Benchmark product",
                "manufacturer": "Benchmark Materials",
                "country": "Germany",
                "production_method": "Measured production",
                "environmental_record": {
                    "co2_kg": co2,
                    "water_liters": water,
                    "energy_kwh": energy,
                    "transportation_kg_co2": 40,
                    "recyclability_score": 75,
                    "sustainability_score": score,
                },
            },
        )
        assert response.status_code == 201

    response = client.get("/api/v1/analytics/benchmarks", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["measured_products"] == 3
    assert payload["portfolio"]["category_count"] == 2
    concrete = next(item for item in payload["category_averages"] if item["category"] == "Concrete")
    assert concrete["average_co2"] == 480
    low_carbon = next(item for item in payload["items"] if item["name"] == "Low Carbon Concrete")
    assert low_carbon["co2_vs_category_pct"] == -25
    assert low_carbon["score_vs_category_points"] == 11
    assert low_carbon["co2_percentile"] > 0


def test_compliance_report_builder_scores_evidence_readiness(client: TestClient) -> None:
    auth = register(client, "tenant-compliance", "admin@compliance.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Compliance Facade Panel",
            "category": "Facade",
            "description": "Panel with compliance evidence.",
            "manufacturer": "Compliance Materials",
            "country": "Germany",
            "production_method": "Precast",
            "material_composition": {"cement": 32, "aggregate": 58, "recycled_content_pct": 18},
            "certifications": [{"name": "EPD EN 15804", "status": "verified"}],
            "environmental_record": {
                "co2_kg": 312,
                "water_liters": 820,
                "energy_kwh": 410,
                "transportation_kg_co2": 35,
                "recyclability_score": 78,
                "sustainability_score": 82,
            },
        },
    )
    product_id = created.json()["id"]

    response = client.post(
        "/api/v1/compliance/reports",
        headers=headers,
        json={"product_id": product_id, "sections": ["product_identity", "environmental_metrics", "materials"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_score"] == 100
    assert payload["report_json"]["schema"] == "compliance-report.v1"
    assert "Compliance Facade Panel" in payload["markdown"]
    assert all(check["status"] == "ready" for check in payload["checks"])


def test_india_compliance_report_scores_local_evidence_and_verification(client: TestClient) -> None:
    auth = register(client, "tenant-india-compliance", "admin@india-compliance.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "India Low Carbon Cement",
            "category": "Cement",
            "description": "Blended cement for Indian infrastructure buyers.",
            "manufacturer": "India Compliance Materials",
            "country": "India",
            "production_method": "Blended cement grinding",
            "declared_unit": "1 t",
            "manufacturing_site": "Nagpur Grinding Unit",
            "plant_code": "NGP-01",
            "product_standard": "IS 1489 aligned internal dataset",
            "pcr": "Construction products PCR",
            "geography": "India",
            "material_composition": {"clinker": 55, "fly_ash": 30, "gypsum": 5},
            "material_components": [
                {
                    "material_name": "Clinker",
                    "category": "Cementitious",
                    "percentage": 55,
                    "recycled_content_pct": 0,
                    "bio_based_content_pct": 0,
                    "supplier": "Nagpur Kiln",
                    "origin_country": "India",
                    "evidence_reference": "Supplier declaration 2026",
                    "sort_order": 0,
                },
                {
                    "material_name": "Fly ash",
                    "category": "SCM",
                    "percentage": 30,
                    "recycled_content_pct": 100,
                    "bio_based_content_pct": 0,
                    "supplier": "Thermal power supplier",
                    "origin_country": "India",
                    "evidence_reference": "Dispatch note FA-2026",
                    "sort_order": 1,
                },
            ],
            "certifications": [{"name": "Internal EPD readiness pack", "status": "verified"}],
            "environmental_record": {
                "co2_kg": 620,
                "water_liters": 900,
                "energy_kwh": 980,
                "transportation_kg_co2": 72,
                "recyclability_score": 68,
                "sustainability_score": 74,
            },
        },
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    submitted = client.post(
        "/api/v1/verifications",
        headers=headers,
        json={
            "product_id": product_id,
            "evidence_summary": "Environmental metrics, material suppliers, and certificate pack reviewed.",
        },
    )
    assert submitted.status_code == 201, submitted.text
    reviewed = client.patch(
        f"/api/v1/verifications/{submitted.json()['id']}/review",
        headers=headers,
        json={"status": "approved", "reviewer_notes": "Ready for Indian buyer evidence pack."},
    )
    assert reviewed.status_code == 200, reviewed.text

    response = client.post(
        "/api/v1/compliance/india/reports",
        headers=headers,
        json={"product_id": product_id, "sections": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["readiness_score"] == 100
    assert payload["report_json"]["schema"] == "india-compliance-readiness.v1"
    assert payload["report_json"]["jurisdiction"] == "India"
    assert "India Compliance Readiness Report" in payload["markdown"]
    assert all(check["status"] == "ready" for check in payload["checks"])


def test_professional_report_packs_are_persisted_and_tenant_scoped(client: TestClient) -> None:
    auth = register(client, "tenant-report-pack", "admin@report-pack.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Tender Ready Concrete",
            "category": "Concrete",
            "description": "Concrete mix with professional reporting evidence.",
            "manufacturer": "Report Pack Materials",
            "country": "India",
            "production_method": "Ready-mix batching",
            "material_composition": {"cement": 24, "aggregate": 68, "admixture": 2},
            "certifications": [{"name": "EPD draft", "status": "internal"}],
            "environmental_record": {
                "co2_kg": 285,
                "water_liters": 640,
                "energy_kwh": 310,
                "transportation_kg_co2": 42,
                "recyclability_score": 76,
                "sustainability_score": 80,
            },
        },
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    created_pack = client.post(
        "/api/v1/compliance/report-packs",
        headers=headers,
        json={
            "product_id": product_id,
            "sections": ["product_identity", "environmental_metrics", "materials"],
            "report_type": "standard",
            "title": "Tender evidence pack",
        },
    )

    assert created_pack.status_code == 201, created_pack.text
    pack = created_pack.json()
    assert pack["title"] == "Tender evidence pack"
    assert pack["product_id"] == product_id
    assert pack["readiness_score"] == 100
    assert pack["report_json"]["schema"] == "compliance-report.v1"
    assert "Tender Ready Concrete" in pack["markdown"]

    listed = client.get(
        f"/api/v1/compliance/report-packs?product_id={product_id}",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == pack["id"]

    audit_logs = client.get(
        "/api/v1/organizations/audit-logs?entity_type=professional_report_pack",
        headers=headers,
    )
    assert audit_logs.status_code == 200, audit_logs.text
    assert audit_logs.json()["total"] == 1
    assert audit_logs.json()["items"][0]["description"] == "Created standard report pack"

    other_auth = register(client, "tenant-report-pack-other", "admin@report-pack-other.example")
    other_headers = {"Authorization": f"Bearer {other_auth['access_token']}"}
    isolated = client.get("/api/v1/compliance/report-packs", headers=other_headers)
    assert isolated.status_code == 200, isolated.text
    assert isolated.json()["total"] == 0


def test_lca_calculation_engine_persists_stage_totals_and_history(client: TestClient) -> None:
    auth = register(client, "tenant-lca", "admin@lca.example")
    other = register(client, "tenant-lca-other", "admin@lca-other.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    db = client.app.state.TestingSessionLocal()
    try:
        db.add(
            EmissionFactor(
                id="test-cement-factor",
                name="Test blended cement factor",
                category="Cement",
                lifecycle_stage="A1-A3",
                unit="t",
                factor_kg_co2e=620,
                geography="India",
                source="Test benchmark",
                version="test",
                notes="Unit test factor",
            )
        )
        db.commit()
    finally:
        db.close()

    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "LCA Cement",
            "category": "Cement",
            "description": "Cement product for LCA calculations.",
            "manufacturer": "LCA Materials",
            "country": "India",
            "production_method": "Blended cement grinding",
        },
    )
    product_id = created.json()["id"]

    factors = client.get("/api/v1/lca/emission-factors?search=blended", headers=headers)
    assert factors.status_code == 200
    assert any(item["id"] == "test-cement-factor" for item in factors.json())

    calculated = client.post(
        f"/api/v1/lca/products/{product_id}/calculations",
        headers=headers,
        json={
            "declared_unit": "1 t cement",
            "boundary": "A1-A4 screening",
            "inputs": [
                {
                    "stage": "A1-A3",
                    "activity_name": "Blended cement production",
                    "quantity": 1,
                    "unit": "t",
                    "emission_factor_id": "test-cement-factor",
                    "data_quality": "hybrid",
                },
                {
                    "stage": "A4",
                    "activity_name": "Outbound road freight",
                    "quantity": 120,
                    "unit": "t-km",
                    "emission_factor_kg_co2e": 0.095,
                    "data_quality": "estimated",
                },
            ],
        },
    )

    assert calculated.status_code == 201, calculated.text
    payload = calculated.json()
    assert payload["total_kg_co2e"] == 631.4
    assert payload["stage_totals_json"]["A1-A3"] == 620
    assert payload["stage_totals_json"]["A4"] == 11.4
    assert payload["confidence"] == "estimated"
    assert "clinker" in payload["result_json"]["interpretation"].lower()

    history = client.get(f"/api/v1/lca/products/{product_id}/calculations", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 1

    blocked = client.post(
        f"/api/v1/lca/products/{product_id}/calculations",
        headers=other_headers,
        json={
            "declared_unit": "1 t cement",
            "inputs": [
                {
                    "stage": "A1-A3",
                    "activity_name": "Blocked calculation",
                    "quantity": 1,
                    "unit": "t",
                    "emission_factor_id": "test-cement-factor",
                }
            ],
        },
    )
    assert blocked.status_code == 404


def test_certificate_extraction_captures_structured_fields(client: TestClient) -> None:
    auth = register(client, "tenant-certificate", "admin@certificate.example")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    certificate_text = """
    Environmental Product Declaration
    Program operator: Institut Bauen und Umwelt
    Declaration number: EPD-ABC-2026-001
    Standard: EN 15804 and ISO 14025
    Declared unit: 1 m2 facade panel
    Valid until: 2029-12-31
    GWP-total A1-A3: 312.4 kg CO2e
    """

    response = client.post(
        "/api/v1/certificates/extract",
        headers=headers,
        files={"file": ("facade_epd.txt", certificate_text, "text/plain")},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["certification_name"] == "EPD EN 15804"
    assert payload["expiry_date"] == "2029-12-31"
    assert payload["emission_value"] == 312.4
    assert payload["extracted_json"]["workflow"] == "pdf_text_field_extraction"
    assert payload["extracted_json"]["fields"]["issuer"] == "Institut Bauen und Umwelt"
    assert payload["extracted_json"]["fields"]["declaration_number"] == "EPD-ABC-2026-001"
    assert payload["extracted_json"]["fields"]["declared_unit"] == "1 m2 facade panel"
    assert payload["extracted_json"]["overall_confidence"] > 0.7
    assert payload["document_type"] == "epd"
    assert payload["extraction_method"] == "pdf_text_field_extraction"
    assert payload["extraction_confidence"] > 0.7
    assert payload["field_confidence_json"]["certification_name"] == 0.9
    assert "EPD-ABC-2026-001" in payload["evidence_json"]["declaration_number"]
    assert payload["status"] == "needs_review"

    reviewed = client.patch(
        f"/api/v1/certificates/{payload['id']}",
        headers=headers,
        json={
            "status": "approved",
            "review_notes": "Verified against uploaded EPD declaration.",
            "document_type": "epd",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["review_notes"] == "Verified against uploaded EPD declaration."
    assert reviewed.json()["reviewed_by_user_id"] == auth["user"]["id"]
    assert reviewed.json()["reviewed_at"]
