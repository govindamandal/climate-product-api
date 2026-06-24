from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

LifecycleStage = Literal["A1-A3", "A4", "A5", "B", "C", "D"]
CalculationConfidence = Literal["measured", "hybrid", "estimated"]


class EmissionFactorRead(BaseModel):
    id: str
    organization_id: str | None
    name: str
    category: str
    lifecycle_stage: str
    unit: str
    factor_kg_co2e: float
    geography: str
    source: str
    version: str
    notes: str

    model_config = {"from_attributes": True}


class LcaInputCreate(BaseModel):
    stage: LifecycleStage
    activity_name: str = Field(min_length=2, max_length=160)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    emission_factor_id: str | None = None
    emission_factor_kg_co2e: float | None = Field(default=None, ge=0)
    data_quality: CalculationConfidence = "estimated"
    notes: str = ""

    @model_validator(mode="after")
    def factor_source_required(self) -> "LcaInputCreate":
        if not self.emission_factor_id and self.emission_factor_kg_co2e is None:
            raise ValueError("Provide emission_factor_id or emission_factor_kg_co2e")
        return self


class LcaCalculationCreate(BaseModel):
    declared_unit: str = Field(default="1 unit", min_length=2, max_length=80)
    boundary: str = Field(default="cradle-to-gate", min_length=2, max_length=80)
    method_version: str = Field(default="lca-engine.v1", min_length=2, max_length=40)
    notes: str = ""
    inputs: list[LcaInputCreate] = Field(min_length=1, max_length=80)


class LcaCalculationRead(BaseModel):
    id: str
    organization_id: str
    product_id: str
    created_by_user_id: str | None
    declared_unit: str
    boundary: str
    method_version: str
    total_kg_co2e: float
    confidence: str
    inputs_json: list
    stage_totals_json: dict
    result_json: dict
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LcaCalculationList(BaseModel):
    items: list[LcaCalculationRead]
    total: int
