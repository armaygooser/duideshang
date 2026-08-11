import { describe, expect, it } from "vitest";
import { deduplicateRequirements, formalQuoteReady, nextUnconfirmedField } from "./session";
describe("formalQuoteReady", () => {
  it("locks when high risk requirements remain", () => expect(formalQuoteReady([{ status: "missing", risk_level: "high" }])).toBe(false));
  it("unlocks after all high risk requirements confirm", () => expect(formalQuoteReady([{ status: "confirmed", risk_level: "high" }, { status: "missing", risk_level: "low" }])).toBe(true));
});
describe("nextUnconfirmedField", () => {
  const fields = [
    { field_name: "width", status: "confirmed" },
    { field_name: "font", status: "missing" },
    { field_name: "height", status: "missing" },
  ];
  it("moves forward to the next unanswered question", () => expect(nextUnconfirmedField(fields, "font")).toBe("height"));
  it("wraps around while skipping confirmed questions", () => expect(nextUnconfirmedField(fields, "height")).toBe("font"));
});
describe("deduplicateRequirements", () => {
  it("keeps one field and prefers the safer ambiguous state", () => {
    const result = deduplicateRequirements([
      { field_name: "width_m", status: "missing" },
      { field_name: "width_m", status: "explicit" },
      { field_name: "width_m", status: "ambiguous" },
      { field_name: "height_m", status: "missing" },
    ]);
    expect(result).toEqual([
      { field_name: "width_m", status: "ambiguous" },
      { field_name: "height_m", status: "missing" },
    ]);
  });
});
