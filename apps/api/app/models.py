from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RequirementStatus = Literal["explicit", "ambiguous", "missing", "suggested", "confirmed", "changed"]
RiskLevel = Literal["low", "medium", "high"]
ProviderChoice = Literal["deepseek", "local-demo"]


class RequirementOption(BaseModel):
    value: str
    label: str
    description: str
    preview: str | None = None


class RequirementField(BaseModel):
    field_name: str
    display_name: str
    value: str | float | bool | None = None
    status: RequirementStatus
    source_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    affects_price: bool = False
    affects_delivery: bool = False
    clarification_question: str | None = None
    options: list[RequirementOption] = []
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


class Highlight(BaseModel):
    text: str
    kind: Literal["explicit", "ambiguous"]
    field_name: str


class AnalysisResult(BaseModel):
    explicit_requirements: list[RequirementField]
    ambiguities: list[RequirementField]
    missing_requirements: list[RequirementField]
    suggested_questions: list[str]
    unsupported_assumptions: list[str]
    highlights: list[Highlight]
    provider: str = "local-demo"
    mode: Literal["agent", "demo"] = "demo"
    degraded: bool = False
    notice: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    provider: ProviderChoice | None = None


class RefineRequest(BaseModel):
    original_text: str = Field(min_length=1, max_length=5000)
    target_field: RequirementField
    answer: str = Field(min_length=1, max_length=1000)
    requirements: list[RequirementField]
    provider: ProviderChoice | None = None


class RefineResult(BaseModel):
    requirement: RequirementField
    accepted: bool
    message: str
    provider: str = "local-demo"
    mode: Literal["agent", "demo"] = "demo"
    degraded: bool = False
    notice: str | None = None


class ProviderStatus(BaseModel):
    requested_provider: str
    active_provider: str
    mode: Literal["agent", "demo"]
    configured: bool
    model: str | None = None


class QuoteInput(BaseModel):
    product_type: str
    width_m: float = Field(gt=0, le=50)
    height_m: float = Field(gt=0, le=20)
    install_height_m: float = Field(ge=0, le=100)
    removal_required: bool
    transport_zone: str
    deadline_type: str
    tax_required: bool
    confirmed_fields: list[str]
    manual_adjustment: float = 0
    adjustment_reason: str | None = None
    merchant_quote_total: float | None = Field(default=None, gt=0)
    merchant_quote_note: str | None = Field(default=None, max_length=500)


class QuoteItem(BaseModel):
    item_name: str
    specification: str
    quantity: float
    unit: str
    unit_price: float
    unit_price_high: float | None = None
    subtotal: float
    subtotal_high: float | None = None
    pricing_rule: str
    price_source: str
    updated_at: datetime
    assumptions: list[str] = []
    price_type: Literal["catalog", "market_reference"] = "catalog"


class QuoteResult(BaseModel):
    status: Literal["formal", "indicative", "merchant_review"] = "formal"
    version: str
    items: list[QuoteItem]
    subtotal: float
    tax: float
    total: float
    estimated_total_low: float | None = None
    estimated_total_high: float | None = None
    pricing_coverage: Literal["catalog", "market_reference"] = "catalog"
    customization_reasons: list[str] = []
    assumptions: list[str]
    exclusions: list[str]
    acceptance_criteria: list[str]
    disclaimer: str
    requires_manual_review: bool = True
