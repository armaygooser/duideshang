export function formalQuoteReady(items: Array<{status: string; risk_level: string}>) { return !items.some((item) => item.risk_level === "high" && item.status !== "confirmed"); }

export function nextUnconfirmedField(
  items: Array<{ field_name: string; status: string }>,
  currentField: string,
) {
  const currentIndex = items.findIndex((item) => item.field_name === currentField);
  const ordered = [...items.slice(currentIndex + 1), ...items.slice(0, Math.max(currentIndex, 0))];
  return ordered.find((item) => item.status !== "confirmed")?.field_name ?? null;
}

export function deduplicateRequirements<T extends { field_name: string; status: string }>(items: T[]) {
  const priority: Record<string, number> = { ambiguous: 4, explicit: 3, suggested: 2, missing: 1 };
  const unique = new Map<string, T>();
  for (const item of items) {
    const current = unique.get(item.field_name);
    if (!current || (priority[item.status] || 0) > (priority[current.status] || 0)) {
      unique.set(item.field_name, item);
    }
  }
  return [...unique.values()];
}
