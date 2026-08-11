import type { AgentActivity, Analysis, PreliminarySummary, ProviderChoice, ProviderStatus, Quote, RefineResult, Requirement } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export async function analyzeText(text: string): Promise<Analysis> {
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  if (!res.ok) throw new Error("需求分析服务暂时不可用");
  return res.json();
}
export async function analyzeTextStream(text: string, options: { provider: ProviderChoice; signal: AbortSignal; onEvent: (event: string, data: AgentActivity | { summary: PreliminarySummary }) => void }): Promise<Analysis> {
  const res = await fetch(`${API_BASE}/api/analyze/stream`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify({ text, provider: options.provider }), signal: options.signal });
  if (!res.ok || !res.body) throw new Error("需求分析服务暂时不可用");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = block.match(/^event:\s*(.+)$/m)?.[1] || "message";
      const raw = block.match(/^data:\s*(.+)$/m)?.[1];
      if (raw) {
        const data = JSON.parse(raw) as AgentActivity & { summary?: PreliminarySummary; message?: string };
        if (event === "result") return data as unknown as Analysis;
        if (event === "error") throw new Error(data.message || "需求分析失败");
        options.onEvent(event, data.summary ? { summary: data.summary } : data);
      }
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  throw new Error("分析连接已结束，请重试");
}
export async function createQuote(payload: Record<string, unknown>): Promise<Quote> {
  const res = await fetch(`${API_BASE}/api/quote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!res.ok) { const data = await res.json(); throw new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "报价失败"); }
  return res.json();
}
export async function getProviderStatus(provider?: ProviderChoice): Promise<ProviderStatus> {
  const res = await fetch(`${API_BASE}/api/provider${provider ? `?provider=${provider}` : ""}`);
  if (!res.ok) throw new Error("无法读取 Agent 状态");
  return res.json();
}
export async function refineRequirement(payload: { original_text: string; target_field: Requirement; answer: string; requirements: Requirement[]; provider: ProviderChoice }): Promise<RefineResult> {
  const res = await fetch(`${API_BASE}/api/refine`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error("Agent 无法理解这条自定义回答");
  return res.json();
}
