from fastapi import APIRouter

from app.api.v1 import (
    ai,
    analytics,
    auth,
    billing,
    certificates,
    compliance,
    integrations,
    lca,
    operations,
    organizations,
    passports,
    platform,
    products,
    verifications,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(billing.router)
api_router.include_router(organizations.router)
api_router.include_router(products.router)
api_router.include_router(passports.router)
api_router.include_router(analytics.router)
api_router.include_router(ai.router)
api_router.include_router(certificates.router)
api_router.include_router(compliance.router)
api_router.include_router(integrations.router)
api_router.include_router(lca.router)
api_router.include_router(verifications.router)
api_router.include_router(operations.router)
api_router.include_router(platform.router)
