import { describe, expect, it } from "vitest";

import { shouldUpgradeStockDetail } from "@/components/pages/useStockDetailFlow";
import type { StockDetail } from "@/lib/types";

describe("stock detail progressive upgrade", () => {
  it("종목 상세 자체가 partial이면 full 업그레이드를 시도한다", () => {
    expect(shouldUpgradeStockDetail({ partial: true } as StockDetail)).toBe(true);
  });

  it("상세 응답은 완성됐어도 이번 주 판단이 partial이면 full 업그레이드를 시도한다", () => {
    expect(
      shouldUpgradeStockDetail({
        partial: false,
        weekly_trade_plan: {
          partial: true,
        },
      } as StockDetail),
    ).toBe(true);
  });

  it("상세와 이번 주 판단이 모두 완성된 경우 불필요한 full 재요청을 하지 않는다", () => {
    expect(
      shouldUpgradeStockDetail({
        partial: false,
        weekly_trade_plan: {
          partial: false,
        },
      } as StockDetail),
    ).toBe(false);
  });
});
