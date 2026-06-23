from fastapi import APIRouter

from app.api.v1 import ai, analytics, auth, certificates, organizations, passports, platform, products

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(products.router)
api_router.include_router(passports.router)
api_router.include_router(analytics.router)
api_router.include_router(ai.router)
api_router.include_router(certificates.router)
api_router.include_router(platform.router)
