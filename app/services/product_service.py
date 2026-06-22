import csv
from io import StringIO

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.product import EnvironmentalRecord, Product
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
            image_url=payload.image_url,
            material_composition=payload.material_composition,
            certifications=payload.certifications,
        )
        self.db.add(product)
        self.db.flush()
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
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        AuditService(self.db).record(
            action=AuditAction.UPDATE,
            entity_type="product",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_id=product.id,
            metadata={"fields": list(payload.model_dump(exclude_unset=True).keys())},
        )
        self.db.commit()
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
            image_url=text("image_url") or None,
            material_composition=material_composition,
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
