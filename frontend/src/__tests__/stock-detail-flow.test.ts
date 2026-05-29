import { describe, expect, it } from "vitest";

import {
  STOCK_DETAIL_AUTO_RETRY_DELAYS_MS,
  chooseUsefulStockDetailSnapshot,
  isStockDetailShellSnapshot,
  shouldAutoRetryStockDetail,
  shouldUpgradeStockDetail,
} from "@/components/pages/useStockDetailFlow";
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

  it("memory guard shell은 백엔드 warm 이후 자동 재시도 대상으로 본다", () => {
    const shell = {
      partial: true,
      fallback_reason: "stock_memory_guard",
      weekly_trade_plan: {
        partial: true,
        fallback_reason: "stock_memory_guard",
      },
    } as StockDetail;

    expect(isStockDetailShellSnapshot(shell)).toBe(true);
    expect(shouldAutoRetryStockDetail(shell, 0)).toBe(true);
  });

  it("자동 재시도는 제한 횟수를 넘기지 않는다", () => {
    expect(
      shouldAutoRetryStockDetail(
        {
          partial: true,
          fallback_reason: "stock_minimal_shell",
        } as StockDetail,
        STOCK_DETAIL_AUTO_RETRY_DELAYS_MS.length,
      ),
    ).toBe(false);
  });

  it("숫자가 있는 quick 판단은 shell 재시도 대상으로 보지 않는다", () => {
    expect(
      shouldAutoRetryStockDetail(
        {
          partial: true,
          fallback_reason: "stock_quick_distributional",
          weekly_trade_plan: {
            partial: true,
            fallback_reason: "stock_quick_distributional",
            buy_price: 100,
            sell_price: 112,
            stop_loss: 94,
          },
        } as StockDetail,
        0,
      ),
    ).toBe(false);
  });

  it("재시도 응답이 shell이면 기존 숫자 판단을 덮어쓰지 않는다", () => {
    const current = {
      partial: true,
      fallback_reason: "stock_quick_distributional",
      weekly_trade_plan: {
        partial: true,
        buy_price: 100,
        sell_price: 112,
        stop_loss: 94,
      },
    } as StockDetail;
    const next = {
      partial: true,
      fallback_reason: "stock_memory_guard",
      weekly_trade_plan: {
        partial: true,
        fallback_reason: "stock_memory_guard",
      },
    } as StockDetail;

    expect(chooseUsefulStockDetailSnapshot(current, next)).toBe(current);
  });

  it("shell 뒤에 숫자 판단이 오면 새 응답으로 교체한다", () => {
    const current = {
      partial: true,
      fallback_reason: "stock_memory_guard",
      weekly_trade_plan: {
        partial: true,
        fallback_reason: "stock_memory_guard",
      },
    } as StockDetail;
    const next = {
      partial: true,
      fallback_reason: "stock_quick_distributional",
      weekly_trade_plan: {
        partial: true,
        fallback_reason: "stock_quick_distributional",
        buy_price: 100,
        sell_price: 112,
        stop_loss: 94,
      },
    } as StockDetail;

    expect(chooseUsefulStockDetailSnapshot(current, next)).toBe(next);
  });
});
