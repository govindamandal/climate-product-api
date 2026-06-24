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


@router.get("/benchmarks")
def benchmarks(user: CurrentUser, db: DbSession) -> dict:
    if not user.organization_id:
        return {"items": [], "category_averages": [], "portfolio": {"measured_products": 0}}
    return build_benchmarks(user.organization_id, db)


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
            "image_url": product.image_url,
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


def build_benchmarks(organization_id: str, db: DbSession) -> dict:
    products = db.scalars(
        select(Product)
        .options(selectinload(Product.environmental_records))
        .where(Product.organization_id == organization_id)
    ).all()
    latest_records = [
        (product, product.environmental_records[0])
        for product in products
        if product.environmental_records
    ]
    category_buckets: dict[str, list[tuple[Product, EnvironmentalRecord]]] = {}
    for product, record in latest_records:
        category_buckets.setdefault(product.category, []).append((product, record))

    category_averages = [
        {
            "category": category,
            "measured_products": len(rows),
            "average_co2": round(sum(row.co2_kg for _, row in rows) / len(rows), 2),
            "average_water": round(sum(row.water_liters for _, row in rows) / len(rows), 2),
            "average_energy": round(sum(row.energy_kwh for _, row in rows) / len(rows), 2),
            "average_score": round(sum(row.sustainability_score for _, row in rows) / len(rows), 1),
        }
        for category, rows in sorted(category_buckets.items())
        if rows
    ]
    category_lookup = {item["category"]: item for item in category_averages}
    co2_values = [record.co2_kg for _, record in latest_records]
    water_values = [record.water_liters for _, record in latest_records]
    energy_values = [record.energy_kwh for _, record in latest_records]
    score_values = [record.sustainability_score for _, record in latest_records]

    items = []
    for product, record in latest_records:
        category = category_lookup[product.category]
        items.append(
            {
                "product_id": product.id,
                "name": product.name,
                "category": product.category,
                "manufacturer": product.manufacturer,
                "image_url": product.image_url,
                "co2_kg": record.co2_kg,
                "water_liters": record.water_liters,
                "energy_kwh": record.energy_kwh,
                "transportation_kg_co2": record.transportation_kg_co2,
                "sustainability_score": record.sustainability_score,
                "co2_percentile": percentile_rank(co2_values, record.co2_kg, lower_is_better=True),
                "water_percentile": percentile_rank(water_values, record.water_liters, lower_is_better=True),
                "energy_percentile": percentile_rank(energy_values, record.energy_kwh, lower_is_better=True),
                "score_percentile": percentile_rank(score_values, record.sustainability_score, lower_is_better=False),
                "category_average_co2": category["average_co2"],
                "category_average_water": category["average_water"],
                "category_average_energy": category["average_energy"],
                "category_average_score": category["average_score"],
                "co2_vs_category_pct": percent_delta(record.co2_kg, float(category["average_co2"])),
                "water_vs_category_pct": percent_delta(record.water_liters, float(category["average_water"])),
                "energy_vs_category_pct": percent_delta(record.energy_kwh, float(category["average_energy"])),
                "score_vs_category_points": round(record.sustainability_score - float(category["average_score"]), 1),
            }
        )
    items.sort(key=lambda item: (item["co2_percentile"], item["score_percentile"]), reverse=True)

    return {
        "items": items,
        "category_averages": category_averages,
        "portfolio": {
            "measured_products": len(latest_records),
            "category_count": len(category_averages),
            "best_carbon_product_id": min(latest_records, key=lambda item: item[1].co2_kg)[0].id
            if latest_records
            else None,
            "best_score_product_id": max(latest_records, key=lambda item: item[1].sustainability_score)[0].id
            if latest_records
            else None,
        },
    }


def percentile_rank(values: list[float | int], value: float | int, *, lower_is_better: bool) -> int:
    if not values:
        return 0
    better_or_equal = sum(1 for item in values if item >= value) if lower_is_better else sum(1 for item in values if item <= value)
    return round((better_or_equal / len(values)) * 100)


def percent_delta(value: float, average: float) -> float:
    if average == 0:
        return 0.0
    return round(((value - average) / average) * 100, 1)
