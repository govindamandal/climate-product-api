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


class ProductMaterialComponentBase(BaseModel):
    material_name: str = Field(min_length=2, max_length=160)
    category: str = Field(default="", max_length=100)
    percentage: float = Field(ge=0, le=100)
    recycled_content_pct: float = Field(default=0, ge=0, le=100)
    bio_based_content_pct: float = Field(default=0, ge=0, le=100)
    supplier: str = Field(default="", max_length=160)
    origin_country: str = Field(default="", max_length=80)
    evidence_reference: str = Field(default="", max_length=240)
    sort_order: int = Field(default=0, ge=0)


class ProductMaterialComponentCreate(ProductMaterialComponentBase):
    pass


class ProductMaterialComponentRead(ProductMaterialComponentBase):
    id: str
    product_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=100)
    description: str = ""
    manufacturer: str = Field(min_length=2, max_length=160)
    country: str = Field(min_length=2, max_length=80)
    production_method: str = Field(min_length=2, max_length=180)
    product_code: str = Field(default="", max_length=80)
    declared_unit: str = Field(default="1 unit", min_length=1, max_length=80)
    functional_unit: str = Field(default="", max_length=180)
    lifecycle_scope: str = Field(default="cradle-to-gate", min_length=2, max_length=80)
    reference_service_life_years: int | None = Field(default=None, ge=0, le=200)
    manufacturing_site: str = Field(default="", max_length=180)
    plant_code: str = Field(default="", max_length=80)
    product_standard: str = Field(default="", max_length=160)
    pcr: str = Field(default="", max_length=180)
    geography: str = Field(default="", max_length=120)
    data_quality: str = Field(default="estimated", max_length=40)
    technical_properties: dict = Field(default_factory=dict)
    image_url: str | None = None
    material_composition: dict = Field(default_factory=dict)
    material_components: list[ProductMaterialComponentCreate] = Field(default_factory=list)
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
    product_code: str | None = Field(default=None, max_length=80)
    declared_unit: str | None = Field(default=None, min_length=1, max_length=80)
    functional_unit: str | None = Field(default=None, max_length=180)
    lifecycle_scope: str | None = Field(default=None, min_length=2, max_length=80)
    reference_service_life_years: int | None = Field(default=None, ge=0, le=200)
    manufacturing_site: str | None = Field(default=None, max_length=180)
    plant_code: str | None = Field(default=None, max_length=80)
    product_standard: str | None = Field(default=None, max_length=160)
    pcr: str | None = Field(default=None, max_length=180)
    geography: str | None = Field(default=None, max_length=120)
    data_quality: str | None = Field(default=None, max_length=40)
    technical_properties: dict | None = None
    image_url: str | None = None
    material_composition: dict | None = None
    material_components: list[ProductMaterialComponentCreate] | None = None
    certifications: list[dict] | None = None


class ProductRead(ProductBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    environmental_records: list[EnvironmentalRecordRead] = []
    material_components: list[ProductMaterialComponentRead] = []

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


class PassportShareRead(BaseModel):
    id: str
    product_id: str
    token: str
    share_url: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicPassportRead(PassportRead):
    share: PassportShareRead
