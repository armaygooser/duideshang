"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Bot, Check, CheckCircle2, ChevronRight, CircleStop, Clipboard, Clock3, FileText, History, Loader2, LockKeyhole, MessageSquareText, Printer, ScanText, ShieldCheck, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { analyzeTextStream, createQuote, getProviderStatus, refineRequirement } from "@/lib/api";
import { deduplicateRequirements, formalQuoteReady, nextUnconfirmedField } from "@/lib/session";
import type { AgentActivity, Analysis, Change, PreliminarySummary, ProviderChoice, ProviderStatus, Quote, Requirement } from "@/lib/types";

const DEMOS = [
  ["标准门头询价", "想做个三米左右的门头，正规大气一点，要能发光，预算四五千，下周五前弄好。"],
  ["参照物模糊", "跟隔壁那个差不多，但是高级一点。"],
  ["预算优先", "预算四千，材料你看着办。"],
  ["交付节点", "下周五之前做好。"],
  ["明确字体", "我要黑体。"],
  ["高度模糊", "就在二楼装，应该不高。"],
] as const;

const VALUE_OPTIONS: Record<string, Array<[string, string]>> = {
  height_m: [["1.2", "1.2 米"], ["1.5", "1.5 米"], ["1.8", "1.8 米"]],
  install_height_m: [["3.5", "3.5 米"], ["4.5", "4.5 米"], ["6", "6 米"]],
  wall_material: [["brick", "砖墙"], ["aluminum", "铝塑板"], ["glass", "玻璃"]],
  removal_required: [["false", "无需拆除"], ["true", "需要拆除"]],
  power_available: [["true", "已有可用电源"], ["false", "需要新增电源"]],
  transport_zone: [["城区", "城区"], ["郊区", "郊区"]],
  tax_required: [["false", "不开发票"], ["true", "需要开票"]],
  lighting_required: [["acrylic_frontlit", "亚克力正面发光字"], ["stainless_backlit", "不锈钢背发光字"]],
};

function normalizeValue(field: string, value: string): string | number | boolean {
  if (["width_m", "height_m", "install_height_m"].includes(field)) return Number(value);
  if (["removal_required", "power_available", "tax_required"].includes(field)) return value === "true";
  return value;
}

function displayValue(value: Requirement["value"]) {
  if (value === true) return "是";
  if (value === false) return "否";
  return value === null || value === undefined || value === "" ? "待确认" : String(value);
}

export default function Home() {
  const [text, setText] = useState<string>(DEMOS[0][1]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [activeField, setActiveField] = useState<string | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [activities, setActivities] = useState<AgentActivity[]>([]);
  const [preliminary, setPreliminary] = useState<PreliminarySummary | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [customAnswers, setCustomAnswers] = useState<Record<string, string>>({});
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [providerChoice, setProviderChoice] = useState<ProviderChoice>("deepseek");
  const [agentNotice, setAgentNotice] = useState("");
  const [refining, setRefining] = useState(false);
  const analysisController = useRef<AbortController | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("duideshang-session");
    if (!saved) return;
    // Restoring browser-owned session state is the intended external synchronization here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { const session = JSON.parse(saved); setText(session.text || DEMOS[0][1]); setRequirements(session.requirements || []); setChanges(session.changes || []); setQuote(session.quote || null); } catch { localStorage.removeItem("duideshang-session"); }
  }, []);
  useEffect(() => { if (requirements.length) localStorage.setItem("duideshang-session", JSON.stringify({ text, requirements, changes, quote })); }, [text, requirements, changes, quote]);
  useEffect(() => {
    const savedProvider = localStorage.getItem("duideshang-provider") as ProviderChoice | null;
    const selected = savedProvider === "local-demo" ? "local-demo" : "deepseek";
    // Browser-owned preference is restored once at startup.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProviderChoice(selected);
    getProviderStatus(selected).then(setProviderStatus).catch(() => setProviderStatus(null));
  }, []);
  useEffect(() => {
    if (!analyzing) return;
    const startedAt = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 250);
    return () => window.clearInterval(timer);
  }, [analyzing]);

  async function runAnalysis(nextText = text) {
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    setAnalyzing(true); setError(""); setQuote(null); setCustomAnswers({}); setAgentNotice(""); setActivities([]); setPreliminary(null); setElapsed(0);
    try {
      const result = await analyzeTextStream(nextText, {
        provider: providerChoice,
        signal: controller.signal,
        onEvent: (event, data) => {
          if (event === "preliminary" && "summary" in data) { setPreliminary(data.summary); return; }
          if ("label" in data) setActivities((current) => current.some((item) => item.stage === data.stage && item.label === data.label) ? current : [...current, data]);
        },
      });
      const all = deduplicateRequirements([...result.ambiguities, ...result.missing_requirements, ...result.explicit_requirements]);
      setAnalysis(result); setRequirements(all); setChanges([]); setActiveField(all[0]?.field_name || null);
      setProviderStatus({ requested_provider: result.provider, active_provider: result.provider, mode: result.mode, configured: !result.degraded, model: result.mode === "agent" ? "deepseek-v4-flash" : null });
      setAgentNotice(result.notice || "");
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") setAgentNotice("已取消本次分析。你可以修改原话后重新开始。");
      else setError(e instanceof Error ? `${e.message}。请确认本地 API 已启动（演示模式无需密钥）。` : "分析失败");
    } finally {
      if (analysisController.current === controller) analysisController.current = null;
      setAnalyzing(false);
    }
  }

  function cancelAnalysis() { analysisController.current?.abort(); }

  function changeProvider(next: ProviderChoice) {
    setProviderChoice(next);
    localStorage.setItem("duideshang-provider", next);
    setAgentNotice("");
    getProviderStatus(next).then(setProviderStatus).catch(() => setProviderStatus(null));
  }

  function confirm(fieldName: string, rawValue: string, isCustom = false) {
    const previous = requirements.find((item) => item.field_name === fieldName);
    const nextValue = isCustom ? rawValue.trim() : normalizeValue(fieldName, rawValue);
    const nextField = nextUnconfirmedField(requirements, fieldName);
    if (previous?.status === "confirmed" && previous.value !== nextValue) {
      setChanges((list) => [{ id: crypto.randomUUID(), field: previous.display_name, from: previous.value, to: nextValue, at: new Date().toLocaleString("zh-CN") }, ...list]);
    }
    setRequirements((current) => current.map((item) => {
      if (item.field_name !== fieldName) return item;
      return { ...item, value: nextValue, status: item.status === "confirmed" && item.value !== nextValue ? "changed" : "confirmed", confirmed_by: "门店操作员", confirmed_at: new Date().toISOString() };
    }));
    setQuote(null);
    setTimeout(() => setRequirements((current) => current.map((item) => item.field_name === fieldName && item.status === "changed" ? { ...item, status: "confirmed" } : item)), 350);
    if (nextField) setTimeout(() => setActiveField(nextField), 180);
  }

  async function confirmCustom(item: Requirement) {
    const answer = customAnswers[item.field_name]?.trim();
    if (!answer) return;
    setRefining(true); setError(""); setAgentNotice("");
    try {
      const result = await refineRequirement({ original_text: text, target_field: item, answer, requirements, provider: providerChoice });
      setProviderStatus((current) => ({ requested_provider: result.provider, active_provider: result.provider, mode: result.mode, configured: !result.degraded, model: result.mode === "agent" ? current?.model || "deepseek-v4-flash" : null }));
      setAgentNotice(result.notice || result.message);
      if (!result.accepted) {
        setRequirements((current) => current.map((field) => field.field_name === item.field_name ? result.requirement : field));
        return;
      }
      const previous = requirements.find((field) => field.field_name === item.field_name);
      if (previous?.status === "confirmed" && previous.value !== result.requirement.value) {
        setChanges((list) => [{ id: crypto.randomUUID(), field: previous.display_name, from: previous.value, to: result.requirement.value, at: new Date().toLocaleString("zh-CN") }, ...list]);
      }
      const nextField = nextUnconfirmedField(requirements, item.field_name);
      setRequirements((current) => current.map((field) => field.field_name === item.field_name ? result.requirement : field));
      setQuote(null);
      if (nextField) setTimeout(() => setActiveField(nextField), 180);
    } catch (e) { setError(e instanceof Error ? e.message : "自定义回答处理失败"); }
    finally { setRefining(false); }
  }

  function fillDemo() {
    const defaults: Record<string, string> = { product_type: "acrylic_frontlit", lighting_required: "acrylic_frontlit", width_m: "3", height_m: "1.2", install_height_m: "3.5", font_style: "heiti", wall_material: "brick", removal_required: "false", power_available: "true", transport_zone: "城区", tax_required: "false", deadline_type: "standard", install_height_note: "3.5" };
    setRequirements((current) => current.map((item) => ({ ...item, value: normalizeValue(item.field_name, defaults[item.field_name] ?? String(item.value ?? "已确认")), status: "confirmed", confirmed_by: "演示客户", confirmed_at: new Date().toISOString() })));
    setQuote(null); setError("");
  }

  const ready = requirements.length > 0 && formalQuoteReady(requirements);
  const confirmed = requirements.filter((x) => x.status === "confirmed").length;
  const progress = requirements.length ? Math.round(confirmed / requirements.length * 100) : 0;
  const active = requirements.find((x) => x.field_name === activeField) || requirements[0];

  async function requestQuote(merchantQuoteTotal?: number, merchantQuoteNote?: string) {
    setLoading(true); setError("");
    const values = Object.fromEntries(requirements.map((x) => [x.field_name, x.value]));
    try {
      const result = await createQuote({
        product_type: values.product_type || values.lighting_required || "acrylic_frontlit",
        width_m: Number(values.width_m || 3), height_m: Number(values.height_m || 1.2), install_height_m: Number(values.install_height_m || values.install_height_note || 3.5),
        removal_required: Boolean(values.removal_required), transport_zone: values.transport_zone || "城区", deadline_type: values.deadline_type || "standard", tax_required: Boolean(values.tax_required),
        confirmed_fields: ["product_type", "width_m", "height_m", "install_height_m", "removal_required", "transport_zone", "deadline_type", "tax_required", "font_style", "wall_material", "power_available"], manual_adjustment: 0, merchant_quote_total: merchantQuoteTotal, merchant_quote_note: merchantQuoteNote,
      });
      setQuote(result);
    } catch (e) { setError(e instanceof Error ? e.message : "报价失败"); }
    finally { setLoading(false); }
  }

  const wechatCopy = useMemo(() => {
    const lines = requirements.filter((x) => x.status === "confirmed").slice(0, 8).map((x) => `• ${x.display_name}：${displayValue(x.value)}`);
    const priceText = !quote ? "" : quote.status === "indicative" ? `\n市场参考区间：¥${quote.estimated_total_low?.toLocaleString("zh-CN")}–¥${quote.estimated_total_high?.toLocaleString("zh-CN")}（定制工艺，待商家按图纸确认）` : quote.status === "merchant_review" ? `\n商家录入总价：¥${quote.total.toLocaleString("zh-CN")}（待对外确认）` : `\n正式报价合计：¥${quote.total.toLocaleString("zh-CN")}（待人工复核）`;
    return `您好，为避免理解偏差，请确认本次门头需求：\n${lines.join("\n")}${priceText}\n如有一项不准确，请直接指出，我们会留痕并重新报价。`;
  }, [requirements, quote]);

  async function copyWechat() { await navigator.clipboard.writeText(wechatCopy); setCopied(true); setTimeout(() => setCopied(false), 1500); }

  function optionList(item: Requirement) {
    if (item.options.length) {
      const options = item.options.map((x) => [x.value, x.label, x.description, x.preview] as const);
      if (["product_type", "lighting_required"].includes(item.field_name) && !options.some(([value]) => value === "custom")) options.push(["custom", "其他定制工艺", "先给出预算参考，按图纸与现场复核", null]);
      return options;
    }
    if (VALUE_OPTIONS[item.field_name]) return VALUE_OPTIONS[item.field_name].map((x) => [x[0], x[1], "", null] as const);
    if (item.field_name === "width_m") return [["2.8", "2.8 米", "", null], ["3", "3.0 米", "", null], ["3.2", "3.2 米", "", null]] as const;
    return [[String(item.value ?? "已确认"), displayValue(item.value) === "待确认" ? "按现场信息确认" : displayValue(item.value), "人工核对后确认", null]] as const;
  }

  return <main>
    <header className="topbar">
      <div className="brand"><div className="brand-mark">对</div><div><strong>对得上</strong><span>DuiDeShang</span></div></div>
      <div className="top-status"><label className="provider-switch"><span>运行方式</span><select aria-label="选择运行方式" value={providerChoice} onChange={(event) => changeProvider(event.target.value as ProviderChoice)}><option value="deepseek">DeepSeek Agent（AI）</option><option value="local-demo">本地规则库（演示）</option></select></label><Badge className={providerStatus?.mode === "agent" ? "agent-badge" : "demo-badge"}><span className="pulse" />{providerStatus?.mode === "agent" ? `DeepSeek Agent${providerStatus.model ? ` · ${providerStatus.model}` : ""}` : providerChoice === "deepseek" ? "AI 不可用，已降级" : "本地演示模式"}</Badge><span className="save-state"><Check size={14}/> 自动保存</span></div>
    </header>
    <section className="hero no-print"><div><p className="eyebrow">需求对齐工作台</p><h1>先把需求对上，再把价格算清。</h1><p>从客户原话中识别理解偏差，逐项确认后生成可解释、可验收的正式报价。</p></div><div className="hero-stat"><ShieldCheck/><div><strong>确定性报价</strong><span>价格只来自可审计规则库</span></div></div></section>

    <div className="workspace">
      <section className="panel source-panel">
        <div className="panel-head"><div><span className="step">01</span><h2>客户原话</h2></div><Badge>微信询价</Badge></div>
        <div className="demo-picker no-print"><label>演示案例</label><select value={text} onChange={(e) => { setText(e.target.value); setAnalysis(null); setRequirements([]); setQuote(null); }}>{DEMOS.map(([name, value]) => <option key={name} value={value}>{name}</option>)}</select></div>
        <textarea aria-label="客户询价文本" value={text} onChange={(e) => setText(e.target.value)} placeholder="粘贴客户微信询价…" />
        <Button className="analyze no-print" onClick={() => runAnalysis()} disabled={analyzing || !text.trim()}>{analyzing ? <Loader2 className="spin"/> : <Sparkles/>}{analyzing ? "Agent 正在分析" : "识别需要确认的地方"}</Button>
        <div className="legend"><span><i className="dot explicit"/>明确表达</span><span><i className="dot ambiguous"/>存在歧义</span><span><i className="dot missing"/>信息缺失</span></div>
        {analysis && <Card className="highlight-card"><h3><MessageSquareText/>原话证据</h3><div className="original-text">{renderHighlights(text, analysis)}</div><p className="hint">颜色只标记表达状态，不代表系统已经替客户做了决定。</p></Card>}
        {analysis && <Card className="guardrail"><AlertTriangle/><div><strong>系统没有偷偷假设</strong><p>{analysis.unsupported_assumptions.join("；")}</p></div></Card>}
      </section>

      <section className="panel clarify-panel">
        <div className="panel-head"><div><span className="step">02</span><h2>逐项对齐</h2></div>{requirements.length > 0 && <span className="counter">{confirmed}/{requirements.length} 已确认</span>}</div>
        {analyzing ? <AgentActivityView activities={activities} preliminary={preliminary} elapsed={elapsed} onCancel={cancelAnalysis}/> : !requirements.length ? <EmptyState/> : <>
          <div className="progress-row"><Progress value={progress}/><strong>{progress}%</strong></div>
          {agentNotice && <div className={`agent-notice ${analysis?.degraded || providerStatus?.configured === false ? "degraded" : ""}`}><Sparkles/><span>{agentNotice}</span></div>}
          <div className="risk-queue no-print">{requirements.map((item) => <button key={item.field_name} aria-label={`查看${item.display_name}`} className={active?.field_name === item.field_name ? "active" : ""} onClick={() => setActiveField(item.field_name)}><span className={`risk ${item.risk_level}`}/>{item.display_name}{item.status === "confirmed" && <CheckCircle2/>}</button>)}</div>
          {active && <Card className="question-card" key={active.field_name}>
            <div className="question-meta"><Badge className={`risk-badge ${active.risk_level}`}>{active.risk_level === "high" ? "高风险" : active.risk_level === "medium" ? "中风险" : "低风险"}</Badge>{active.affects_price && <span>影响价格</span>}{active.affects_delivery && <span>影响交付</span>}</div>
            <h3>{active.clarification_question || `请确认${active.display_name}`}</h3>
            {active.source_text && <blockquote>客户原话：“{active.source_text}”</blockquote>}
            <div className="options">{optionList(active).map(([value,label,description,preview]) => <button key={value} className={String(active.value) === value && active.status === "confirmed" ? "selected" : ""} onClick={() => confirm(active.field_name, value)}>{preview && <span className={`font-preview ${value}`}>{preview}</span>}<span><strong>{label}</strong>{description && <small>{description}</small>}</span><ChevronRight/></button>)}</div>
            <div className="custom-answer">
              <div><strong>都不合适？填写客户的实际要求</strong><span>自定义内容会原样进入确认单；涉及价格时仍需规则库或人工复核。</span></div>
              <div className="custom-answer-row"><input aria-label={`自定义${active.display_name}`} value={customAnswers[active.field_name] || ""} disabled={refining} onChange={(e) => setCustomAnswers((current) => ({ ...current, [active.field_name]: e.target.value }))} onKeyDown={(e) => { if (e.key === "Enter") void confirmCustom(active); }} placeholder={`输入${active.display_name}的自定义答案…`} /><Button variant="outline" disabled={refining || !customAnswers[active.field_name]?.trim()} onClick={() => void confirmCustom(active)}>{refining ? <Loader2 className="spin"/> : <Sparkles/>}{refining ? "Agent 判断中" : "交给 Agent 确认"}</Button></div>
            </div>
          </Card>}
          <Button variant="outline" className="fill-demo no-print" onClick={fillDemo}><Sparkles/>应用预设确认（演示）</Button>
        </>}
      </section>

      <aside className="panel sheet-panel">
        <div className="panel-head"><div><span className="step">03</span><h2>需求确认单</h2></div><Button variant="ghost" size="sm" onClick={() => window.print()} disabled={!requirements.length}><Printer/>打印</Button></div>
        {!requirements.length ? <p className="sheet-empty">分析后，客户确认的规格会实时出现在这里。</p> : <>
          <div className="sheet-summary"><div className="ring" style={{"--progress": `${progress * 3.6}deg`} as React.CSSProperties}><strong>{progress}%</strong></div><div><strong>{ready ? "可以生成正式报价" : "仍有高风险项待确认"}</strong><span>{ready ? "需求已达到报价门槛" : "系统会阻止带假设的正式报价"}</span></div></div>
          <div className="requirement-list">{requirements.map((item) => <button key={item.field_name} onClick={() => setActiveField(item.field_name)}><span>{item.display_name}</span><strong className={item.status === "confirmed" ? "confirmed" : "pending"}>{displayValue(item.value)}</strong></button>)}</div>
          {!quote ? <div className="quote-lock"><Button size="lg" onClick={() => void requestQuote()} disabled={!ready || loading}>{ready ? <FileText/> : <LockKeyhole/>}{ready ? "生成报价或预算参考" : "完成高风险确认后报价"}</Button><p>常规品类使用门店价目；未覆盖工艺会给出市场参考区间，并保留商家填写位。</p></div> : <QuoteView quote={quote} loading={loading} onMerchantQuote={requestQuote}/>}
          <Card className="wechat"><div className="section-title"><MessageSquareText/><strong>微信确认话术</strong></div><pre>{wechatCopy}</pre><Button variant="outline" onClick={copyWechat}>{copied ? <Check/> : <Clipboard/>}{copied ? "已复制" : "复制话术"}</Button></Card>
          <Card className="history"><div className="section-title"><History/><strong>需求变更</strong><Badge>{changes.length}</Badge></div>{changes.length ? changes.map((x) => <p key={x.id}><span>{x.field}</span>{String(x.from)} → {String(x.to)}<small>{x.at}</small></p>) : <p className="muted">修改已确认字段后，将在这里留下记录。</p>}</Card>
        </>}
      </aside>
    </div>
    {error && <div className="toast"><AlertTriangle/>{error}<button onClick={() => setError("")}>×</button></div>}
    <footer><span>对得上 · 面试演示产品</span><span>规则库 v0.2 · {providerStatus?.mode === "agent" ? "DeepSeek Agent" : "本地 Provider · 无需 API Key"}</span></footer>
  </main>;
}

function renderHighlights(text: string, analysis: Analysis) {
  const matches = analysis.highlights.map((x) => ({ ...x, index: text.indexOf(x.text) })).filter((x) => x.index >= 0).sort((a,b) => a.index-b.index);
  const nodes: React.ReactNode[] = []; let cursor = 0;
  matches.forEach((x, i) => { if (x.index < cursor) return; nodes.push(text.slice(cursor, x.index)); nodes.push(<mark key={`${x.field_name}-${i}`} className={x.kind}>{x.text}</mark>); cursor = x.index + x.text.length; });
  nodes.push(text.slice(cursor)); return nodes;
}

function AgentActivityView({ activities, preliminary, elapsed, onCancel }: { activities: AgentActivity[]; preliminary: PreliminarySummary | null; elapsed: number; onCancel: () => void }) {
  return <div className="agent-activity">
    <div className="activity-heading"><div className="activity-icon"><Bot/></div><div><strong>Agent 正在分析这条询价</strong><span><Clock3/>{elapsed} 秒</span></div><Button variant="outline" size="sm" onClick={onCancel}><CircleStop/>取消</Button></div>
    {preliminary && <div className="preliminary"><ScanText/><span>初步扫描：{preliminary.explicit_count} 项明确表达、{preliminary.ambiguity_count} 项待澄清、{preliminary.missing_count} 项待补充</span></div>}
    <div className="activity-list">{activities.length ? activities.map((item) => <div key={`${item.stage}-${item.label}`}><Check/><span>{item.label}</span></div>) : <div className="pending"><Loader2 className="spin"/><span>正在建立分析连接…</span></div>}</div>
    <p>显示的是 Agent 的真实处理节点；不会虚构进度百分比。</p>
  </div>;
}

function EmptyState() { return <div className="empty"><div><Sparkles/></div><h3>从原话开始，而不是从猜测开始</h3><p>系统会把价格影响大、返工风险高的问题优先排出来。</p><div className="empty-flow"><span>识别歧义</span><ChevronRight/><span>客户确认</span><ChevronRight/><span>锁定报价</span></div></div>; }

function QuoteView({ quote, loading, onMerchantQuote }: { quote: Quote; loading: boolean; onMerchantQuote: (total: number, note: string) => void }) { const [merchantTotal, setMerchantTotal] = useState(""); const [merchantNote, setMerchantNote] = useState(""); const indicative = quote.status === "indicative"; const merchantReview = quote.status === "merchant_review"; const totalText = indicative ? `¥ ${quote.estimated_total_low?.toLocaleString("zh-CN")} – ${quote.estimated_total_high?.toLocaleString("zh-CN")}` : `¥ ${quote.total.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`; return <Card className={`quote ${indicative ? "indicative" : ""}`}><div className="quote-head"><div><Badge>{merchantReview ? "商家录入 · 待对外确认" : indicative ? "市场参考 · 需定制复核" : "正式报价 · 待人工复核"}</Badge><small>{quote.version}</small></div><strong>{totalText}</strong></div>{(indicative || merchantReview) && <div className="quote-reference"><strong>{merchantReview ? "该金额由商家手工录入，发送客户前请再次确认。" : "此为预算参考区间，不会自动形成正式报价。"}</strong>{quote.customization_reasons.map((reason) => <p key={reason}>• {reason}</p>)}</div>}{indicative && <div className="merchant-quote"><strong>老板填写最终定制总价</strong><span>可先留空；填写后会单独留痕，不覆盖市场参考来源。</span><div><input aria-label="商家定制报价总价" inputMode="decimal" value={merchantTotal} onChange={(event) => setMerchantTotal(event.target.value)} placeholder="例如 6800"/><input aria-label="商家报价备注" value={merchantNote} onChange={(event) => setMerchantNote(event.target.value)} placeholder="例如：含不锈钢底板与夜间安装"/><Button variant="outline" disabled={loading || !Number(merchantTotal)} onClick={() => onMerchantQuote(Number(merchantTotal), merchantNote)}>{loading ? <Loader2 className="spin"/> : <Check/>}保存商家报价</Button></div></div>}<div className="quote-items">{quote.items.map((x) => <div key={x.item_name}><span><strong>{x.item_name}</strong><small>{x.specification} · {x.pricing_rule}</small></span><b>{x.subtotal_high ? `¥${x.subtotal.toLocaleString()}–${x.subtotal_high.toLocaleString()}` : `¥${x.subtotal.toLocaleString()}`}</b></div>)}{quote.tax > 0 && <div><span>税费</span><b>{indicative && quote.estimated_total_high ? "按区间含税计算" : `¥${quote.tax.toLocaleString()}`}</b></div>}</div><details><summary>计价假设与不包含项目</summary><h4>计价假设</h4>{quote.assumptions.map((x) => <p key={x}>• {x}</p>)}<h4>不包含</h4>{quote.exclusions.map((x) => <p key={x}>• {x}</p>)}</details><div className="acceptance"><h4><ShieldCheck/>验收标准</h4>{quote.acceptance_criteria.map((x) => <p key={x}><Check/> {x}</p>)}</div><p className="disclaimer">{quote.disclaimer}</p></Card>; }
