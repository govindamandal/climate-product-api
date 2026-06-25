from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import EnvironmentalRecord, Product
from app.repositories.base import Repository


class ProductRepository(Repository[Product]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Product)

    def list_for_org(
        self,
        organization_id: str,
        *,
        search: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        stmt = select(Product).where(Product.organization_id == organization_id)
        count_stmt = select(func.count(Product.id)).where(Product.organization_id == organization_id)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                Product.name.ilike(like)
                | Product.category.ilike(like)
                | Product.manufacturer.ilike(like)
            )
            count_stmt = count_stmt.where(
                Product.name.ilike(like)
                | Product.category.ilike(like)
                | Product.manufacturer.ilike(like)
            )
        if category:
            stmt = stmt.where(Product.category == category)
            count_stmt = count_stmt.where(Product.category == category)
        stmt = (
            stmt.options(
                selectinload(Product.environmental_records),
                selectinload(Product.material_components),
            )
            .order_by(Product.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt)), int(self.db.scalar(count_stmt) or 0)

    def categories_for_org(self, organization_id: str) -> list[str]:
        stmt = (
            select(Product.category)
            .where(Product.organization_id == organization_id)
            .distinct()
            .order_by(Product.category.asc())
        )
        return list(self.db.scalars(stmt))

    def get_for_org(self, organization_id: str, product_id: str) -> Product | None:
        return self.db.scalar(
            select(Product)
            .options(
                selectinload(Product.environmental_records),
                selectinload(Product.material_components),
            )
            .where(Product.organization_id == organization_id, Product.id == product_id)
        )


class EnvironmentalRecordRepository(Repository[EnvironmentalRecord]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, EnvironmentalRecord)
