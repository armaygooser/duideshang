export type Status = "explicit" | "ambiguous" | "missing" | "suggested" | "confirmed" | "changed";
export interface Option { value: string; label: string; description: string; preview?: string | null }
export interface Requirement { field_name: string; display_name: string; value: string | number | boolean | null; status: Status; source_text?: string | null; confidence: number; risk_level: "low" | "medium" | "high"; affects_price: boolean; affects_delivery: boolean; clarification_question?: string | null; options: Option[]; confirmed_by?: string | null; confirmed_at?: string | null }
export interface Highlight { text: string; kind: "explicit" | "ambiguous"; field_name: string }
export interface ProviderMeta { provider: string; mode: "agent" | "demo"; degraded: boolean; notice?: string | null }
export interface ProviderStatus { requested_provider: string; active_provider: string; mode: "agent" | "demo"; configured: boolean; model?: string | null }
export type ProviderChoice = "deepseek" | "local-demo";
export interface Analysis extends ProviderMeta { explicit_requirements: Requirement[]; ambiguities: Requirement[]; missing_requirements: Requirement[]; suggested_questions: string[]; unsupported_assumptions: string[]; highlights: Highlight[] }
export interface AgentActivity { stage: string; label: string; detail?: string }
export interface PreliminarySummary { explicit_count: number; ambiguity_count: number; missing_count: number }
export interface RefineResult extends ProviderMeta { requirement: Requirement; accepted: boolean; message: string }
export interface QuoteItem { item_name: string; specification: string; quantity: number; unit: string; unit_price: number; unit_price_high?: number | null; subtotal: number; subtotal_high?: number | null; pricing_rule: string; price_source: string; assumptions: string[]; price_type?: "catalog" | "market_reference" }
export interface Quote { status: "formal" | "indicative" | "merchant_review"; version: string; items: QuoteItem[]; subtotal: number; tax: number; total: number; estimated_total_low?: number | null; estimated_total_high?: number | null; pricing_coverage: "catalog" | "market_reference"; customization_reasons: string[]; assumptions: string[]; exclusions: string[]; acceptance_criteria: string[]; disclaimer: string; requires_manual_review: boolean }
export interface Change { id: string; field: string; from: unknown; to: unknown; at: string }
