from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.product import (
    EnvironmentalRecordCreate,
    ProductCreate,
    ProductImageUploadResult,
    ProductImportResult,
    ProductList,
    ProductRead,
    ProductUpdate,
)
from app.services.product_service import ProductService
from app.services.storage_service import ProductImageStorage

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductList)
def list_products(
    user: CurrentUser,
    db: DbSession,
    search: str | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProductList:
    return ProductService(db).list_products(
        user, search=search, category=category, page=page, page_size=page_size
    )


@router.post("", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, user: CurrentUser, db: DbSession) -> ProductRead:
    return ProductService(db).create_product(user, payload)


@router.post("/imports/csv", response_model=ProductImportResult, status_code=201)
async def import_products_csv(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> ProductImportResult:
    if not (file.filename or "").endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    return ProductService(db).import_csv(user, await file.read())


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return ProductService(db).get_product(user, product_id)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: str, payload: ProductUpdate, user: CurrentUser, db: DbSession
) -> ProductRead:
    return ProductService(db).update_product(user, product_id, payload)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, user: CurrentUser, db: DbSession) -> None:
    ProductService(db).delete_product(user, product_id)


@router.post("/{product_id}/environmental-records", response_model=ProductRead, status_code=201)
def add_environmental_record(
    product_id: str, payload: EnvironmentalRecordCreate, user: CurrentUser, db: DbSession
) -> ProductRead:
    return ProductService(db).add_environmental_record(user, product_id, payload)


@router.post("/{product_id}/image", response_model=ProductImageUploadResult, status_code=201)
async def upload_product_image(
    product_id: str,
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
) -> ProductImageUploadResult:
    product = ProductService(db).get_product(user, product_id)
    uploaded = await ProductImageStorage(get_settings()).upload_product_image(
        organization_id=product.organization_id,
        product_id=product.id,
        file=file,
    )
    ProductService(db).set_product_image(
        user,
        product_id,
        image_url=uploaded.url,
        image_key=uploaded.key,
    )
    return ProductImageUploadResult(image_url=uploaded.url)
