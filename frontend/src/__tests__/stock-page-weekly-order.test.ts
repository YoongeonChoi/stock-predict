import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("stock detail weekly decision order", () => {
  it("이번 주 판단 카드를 감사/제한 배너보다 먼저 렌더링한다", () => {
    const source = readFileSync(resolve(process.cwd(), "src/components/pages/StockPageClient.tsx"), "utf8");

    expect(source.indexOf("<WeeklyTradePlanCard")).toBeGreaterThan(-1);
    expect(source.indexOf("<PublicAuditStrip")).toBeGreaterThan(-1);
    expect(source.indexOf("<WeeklyTradePlanCard")).toBeLessThan(source.indexOf("<PublicAuditStrip"));
  });
});
