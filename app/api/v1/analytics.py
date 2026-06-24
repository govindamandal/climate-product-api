from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.product import EnvironmentalRecord, Product
from app.services.cache_service import CacheService, analytics_cache_key

router = APIRouter(prefix="/analytics", tags=["Sustainability Analytics"])


@router.get("/summary")
def summary(user: CurrentUser, db: DbSession) -> dict:
    if not user.organization_id:
        return {}
    cache = CacheService()
    cache_key = analytics_cache_key(user.organization_id)
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    payload = build_summary(user.organization_id, db)
    cache.set_json(
        cache_key,
        payload,
        ttl_seconds=get_settings().analytics_cache_ttl_seconds,
    )
    return payload


def build_summary(organization_id: str, db: DbSession) -> dict:
    products = db.scalars(
        select(Product)
        .options(selectinload(Product.environmental_records))
        .where(Product.organization_id == organization_id)
    ).all()
    rows = db.scalars(
        select(EnvironmentalRecord).where(EnvironmentalRecord.organization_id == organization_id)
    ).all()
    latest_records = [
        (product, product.environmental_records[0])
        for product in products
        if product.environmental_records
    ]
    total = len(latest_records) or 1
    category_totals: dict[str, dict[str, float | int | str]] = {}
    for product, record in latest_records:
        bucket = category_totals.setdefault(
            product.category,
            {
                "category": product.category,
                "products": 0,
                "co2": 0.0,
                "water": 0.0,
                "energy": 0.0,
                "score_total": 0.0,
            },
        )
        bucket["products"] = int(bucket["products"]) + 1
        bucket["co2"] = float(bucket["co2"]) + record.co2_kg
        bucket["water"] = float(bucket["water"]) + record.water_liters
        bucket["energy"] = float(bucket["energy"]) + record.energy_kwh
        bucket["score_total"] = float(bucket["score_total"]) + record.sustainability_score

    categories = []
    for bucket in category_totals.values():
        product_count = int(bucket["products"]) or 1
        categories.append(
            {
                "category": bucket["category"],
                "products": product_count,
                "co2": round(float(bucket["co2"]), 2),
                "water": round(float(bucket["water"]), 2),
                "energy": round(float(bucket["energy"]), 2),
                "average_score": round(float(bucket["score_total"]) / product_count, 1),
            }
        )
    categories.sort(key=lambda item: item["co2"], reverse=True)

    hotspots = [
        {
            "product_id": product.id,
            "name": product.name,
            "category": product.category,
            "co2": record.co2_kg,
            "energy": record.energy_kwh,
            "water": record.water_liters,
            "sustainability_score": record.sustainability_score,
        }
        for product, record in sorted(latest_records, key=lambda item: item[1].co2_kg, reverse=True)[
            :5
        ]
    ]

    score_distribution = [
        {"label": "0-49", "count": sum(1 for _, record in latest_records if record.sustainability_score < 50)},
        {
            "label": "50-69",
            "count": sum(1 for _, record in latest_records if 50 <= record.sustainability_score < 70),
        },
        {
            "label": "70-84",
            "count": sum(1 for _, record in latest_records if 70 <= record.sustainability_score < 85),
        },
        {"label": "85-100", "count": sum(1 for _, record in latest_records if record.sustainability_score >= 85)},
    ]

    return {
        "product_count": len(products),
        "measured_product_count": len(latest_records),
        "total_co2": round(sum(record.co2_kg for _, record in latest_records), 2),
        "total_energy": round(sum(record.energy_kwh for _, record in latest_records), 2),
        "total_water": round(sum(record.water_liters for _, record in latest_records), 2),
        "average_sustainability_score": round(
            sum(record.sustainability_score for _, record in latest_records) / total, 1
        ),
        "category_breakdown": categories,
        "hotspots": hotspots,
        "score_distribution": score_distribution,
        "trend": [
            {
                "label": row.recorded_at.strftime("%b %d"),
                "co2": row.co2_kg,
                "energy": row.energy_kwh,
                "water": row.water_liters,
            }
            for row in sorted(rows, key=lambda item: item.recorded_at)[-12:]
        ],
    }
