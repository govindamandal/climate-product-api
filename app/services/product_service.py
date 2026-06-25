import csv
from io import StringIO

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.product import EnvironmentalRecord, Product, ProductMaterialComponent
from app.models.user import User
from app.repositories.products import ProductRepository
from app.schemas.product import (
    EnvironmentalRecordCreate,
    ProductCreate,
    ProductImportError,
    ProductImportResult,
    ProductList,
    ProductUpdate,
)
from app.services.audit_service import AuditService
from app.services.cache_service import CacheService, analytics_cache_key


class ProductService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.products = ProductRepository(db)

    def list_products(
        self,
        user: User,
        *,
        search: str | None,
        category: str | None,
        page: int,
        page_size: int,
    ) -> ProductList:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        items, total = self.products.list_for_org(
            user.organization_id,
            search=search,
            category=category,
            page=page,
            page_size=page_size,
        )
        return ProductList(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            categories=self.products.categories_for_org(user.organization_id),
        )

    def create_product(self, user: User, payload: ProductCreate) -> Product:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        product = Product(
            organization_id=user.organization_id,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            manufacturer=payload.manufacturer,
            country=payload.country,
            production_method=payload.production_method,
            product_code=payload.product_code,
            declared_unit=payload.declared_unit,
            functional_unit=payload.functional_unit,
            lifecycle_scope=payload.lifecycle_scope,
            reference_service_life_years=payload.reference_service_life_years,
            manufacturing_site=payload.manufacturing_site,
            plant_code=payload.plant_code,
            product_standard=payload.product_standard,
            pcr=payload.pcr,
            geography=payload.geography,
            data_quality=payload.data_quality,
            technical_properties=payload.technical_properties,
            image_url=payload.image_url,
            material_composition=payload.material_composition,
            certifications=payload.certifications,
        )
        self.db.add(product)
        self.db.flush()
        self._replace_material_components(user, product, payload.material_components)
        if payload.environmental_record:
            self._create_record(user, product.id, payload.environmental_record)
        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="product",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
        )
        self.db.commit()
        self._invalidate_analytics(user)
        return self.get_product(user, product.id)

    def get_product(self, user: User, product_id: str) -> Product:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        product = self.products.get_for_org(user.organization_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    def update_product(self, user: User, product_id: str, payload: ProductUpdate) -> Product:
        product = self.get_product(user, product_id)
        update_data = payload.model_dump(exclude_unset=True)
        material_components = update_data.pop("material_components", None)
        for field, value in update_data.items():
            setattr(product, field, value)
        if material_components is not None:
            self._replace_material_components(user, product, payload.material_components or [])
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="product",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
            metadata={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        )
        self.db.commit()
        self._invalidate_analytics(user)
        return self.get_product(user, product_id)

    def add_environmental_record(
        self, user: User, product_id: str, payload: EnvironmentalRecordCreate
    ) -> Product:
        product = self.get_product(user, product_id)
        self._create_record(user, product.id, payload)
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="environmental_record",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
        )
        self.db.commit()
        self._invalidate_analytics(user)
        return self.get_product(user, product_id)

    def set_product_image(self, user: User, product_id: str, *, image_url: str, image_key: str) -> Product:
        product = self.get_product(user, product_id)
        product.image_url = image_url
        product.image_key = image_key
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="product_image",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
        )
        self.db.commit()
        self._invalidate_analytics(user)
        return self.get_product(user, product_id)

    def delete_product(self, user: User, product_id: str) -> None:
        product = self.get_product(user, product_id)
        AuditService(self.db).record(
            action=AuditAction.DELETE,
            entity_type="product",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
        )
        self.db.delete(product)
        self.db.commit()
        self._invalidate_analytics(user)

    def import_csv(self, user: User, content: bytes) -> ProductImportResult:
        if not user.organization_id:
            raise HTTPException(status_code=400, detail="User is not attached to an organization")
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

        reader = csv.DictReader(StringIO(decoded))
        required = {"name", "category", "manufacturer", "country", "production_method"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV is missing required columns: {', '.join(sorted(missing))}",
            )

        created = 0
        errors: list[ProductImportError] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                payload = self._row_to_payload(row)
                self.create_product(user, payload)
                created += 1
            except Exception as exc:  # noqa: BLE001 - importing should keep processing valid rows.
                self.db.rollback()
                errors.append(ProductImportError(row=row_number, message=str(exc)))

        AuditService(self.db).record(
            action=AuditAction.CREATE,
            entity_type="product_import",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            metadata={"created": created, "errors": len(errors)},
        )
        self.db.commit()
        self._invalidate_analytics(user)
        return ProductImportResult(created=created, skipped=len(errors), errors=errors)

    def _row_to_payload(self, row: dict[str, str | None]) -> ProductCreate:
        def text(column: str, default: str = "") -> str:
            return (row.get(column) or default).strip()

        def number(column: str) -> float | None:
            raw = text(column)
            return float(raw) if raw else None

        def integer(column: str) -> int | None:
            raw = text(column)
            return int(float(raw)) if raw else None

        environmental_record = None
        if number("co2_kg") is not None:
            environmental_record = EnvironmentalRecordCreate(
                co2_kg=number("co2_kg") or 0,
                water_liters=number("water_liters") or 0,
                energy_kwh=number("energy_kwh") or 0,
                transportation_kg_co2=number("transportation_kg_co2") or 0,
                recyclability_score=integer("recyclability_score") or 0,
                sustainability_score=integer("sustainability_score") or 0,
                notes=text("notes", "Imported from CSV"),
            )

        recycled_content = number("recycled_content_pct")
        material_composition = {"primary": text("category")}
        if recycled_content is not None:
            material_composition["recycled_content_pct"] = recycled_content
        material_components = []
        primary_material = text("primary_material", text("category"))
        primary_pct = number("primary_material_pct")
        if primary_material:
            material_components.append(
                {
                    "material_name": primary_material,
                    "category": text("primary_material_category", text("category")),
                    "percentage": primary_pct if primary_pct is not None else 100,
                    "recycled_content_pct": recycled_content or 0,
                    "supplier": text("primary_material_supplier"),
                    "origin_country": text("primary_material_origin_country", text("country")),
                    "evidence_reference": text("primary_material_evidence_reference"),
                }
            )

        certifications = []
        certification_name = text("certification_name")
        if certification_name:
            certifications.append({"name": certification_name, "status": text("certification_status", "uploaded")})

        return ProductCreate(
            name=text("name"),
            category=text("category"),
            description=text("description"),
            manufacturer=text("manufacturer"),
            country=text("country"),
            production_method=text("production_method"),
            product_code=text("product_code"),
            declared_unit=text("declared_unit", "1 unit"),
            functional_unit=text("functional_unit"),
            lifecycle_scope=text("lifecycle_scope", "cradle-to-gate"),
            reference_service_life_years=integer("reference_service_life_years"),
            manufacturing_site=text("manufacturing_site"),
            plant_code=text("plant_code"),
            product_standard=text("product_standard"),
            pcr=text("pcr"),
            geography=text("geography", text("country")),
            data_quality=text("data_quality", "estimated"),
            technical_properties={},
            image_url=text("image_url") or None,
            material_composition=material_composition,
            material_components=material_components,
            certifications=certifications,
            environmental_record=environmental_record,
        )

    def _create_record(
        self, user: User, product_id: str, payload: EnvironmentalRecordCreate
    ) -> EnvironmentalRecord:
        record = EnvironmentalRecord(
            organization_id=user.organization_id or "",
            product_id=product_id,
            **payload.model_dump(),
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _replace_material_components(
        self,
        user: User,
        product: Product,
        components: list,
    ) -> None:
        for component in list(product.material_components):
            self.db.delete(component)
        self.db.flush()
        for index, component in enumerate(components):
            data = component.model_dump() if hasattr(component, "model_dump") else dict(component)
            self.db.add(
                ProductMaterialComponent(
                    organization_id=user.organization_id or product.organization_id,
                    product_id=product.id,
                    sort_order=data.get("sort_order") or index,
                    material_name=data["material_name"],
                    category=data.get("category") or "",
                    percentage=data["percentage"],
                    recycled_content_pct=data.get("recycled_content_pct") or 0,
                    bio_based_content_pct=data.get("bio_based_content_pct") or 0,
                    supplier=data.get("supplier") or "",
                    origin_country=data.get("origin_country") or "",
                    evidence_reference=data.get("evidence_reference") or "",
                )
            )
        self.db.flush()

    def _invalidate_analytics(self, user: User) -> None:
        if user.organization_id:
            CacheService().delete(analytics_cache_key(user.organization_id))
