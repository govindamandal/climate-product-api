from datetime import datetime

from pydantic import BaseModel, Field


class EnvironmentalRecordBase(BaseModel):
    co2_kg: float = Field(ge=0)
    water_liters: float = Field(ge=0)
    energy_kwh: float = Field(ge=0)
    transportation_kg_co2: float = Field(ge=0)
    recyclability_score: int = Field(ge=0, le=100)
    sustainability_score: int = Field(ge=0, le=100)
    notes: str = ""


class EnvironmentalRecordCreate(EnvironmentalRecordBase):
    pass


class EnvironmentalRecordRead(EnvironmentalRecordBase):
    id: str
    product_id: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=100)
    description: str = ""
    manufacturer: str = Field(min_length=2, max_length=160)
    country: str = Field(min_length=2, max_length=80)
    production_method: str = Field(min_length=2, max_length=180)
    image_url: str | None = None
    material_composition: dict = Field(default_factory=dict)
    certifications: list[dict] = Field(default_factory=list)


class ProductCreate(ProductBase):
    environmental_record: EnvironmentalRecordCreate | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    manufacturer: str | None = Field(default=None, min_length=2, max_length=160)
    country: str | None = Field(default=None, min_length=2, max_length=80)
    production_method: str | None = Field(default=None, min_length=2, max_length=180)
    image_url: str | None = None
    material_composition: dict | None = None
    certifications: list[dict] | None = None


class ProductRead(ProductBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    environmental_records: list[EnvironmentalRecordRead] = []

    model_config = {"from_attributes": True}


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int
    categories: list[str] = []


class ProductImportError(BaseModel):
    row: int
    message: str


class ProductImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[ProductImportError] = []


class ProductImageUploadResult(BaseModel):
    image_url: str


class PassportRead(BaseModel):
    product: ProductRead
    latest_environmental_record: EnvironmentalRecordRead | None
    sustainability_score: int
    passport_json: dict
