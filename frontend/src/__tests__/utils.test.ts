import { describe, it, expect } from "vitest";
import {
  formatNumber,
  formatPct,
  scoreColor,
  changeColor,
  currencySymbol,
  formatPrice,
  formatMarketCap,
} from "@/lib/utils";

describe("formatNumber", () => {
  it("null/undefined를 N/A로 반환한다", () => {
    expect(formatNumber(null)).toBe("N/A");
    expect(formatNumber(undefined)).toBe("N/A");
  });

  it("조 단위를 T 접미어로 축약한다", () => {
    expect(formatNumber(1.5e12)).toBe("1.5T");
  });

  it("억 단위를 B 접미어로 축약한다", () => {
    expect(formatNumber(2.3e9)).toBe("2.3B");
  });

  it("백만 단위를 M 접미어로 축약한다", () => {
    expect(formatNumber(4.7e6)).toBe("4.7M");
  });

  it("소수점 자릿수를 존중한다", () => {
    const result = formatNumber(1234.5678, 1);
    expect(result).toContain("1");
  });
});

describe("formatPct", () => {
  it("null을 N/A로 반환한다", () => {
    expect(formatPct(null)).toBe("N/A");
  });

  it("양수에 + 기호를 붙인다", () => {
    expect(formatPct(3.14)).toBe("+3.14%");
  });

  it("음수에 - 기호를 유지한다", () => {
    expect(formatPct(-2.5)).toBe("-2.50%");
  });

  it("0에 + 기호를 붙인다", () => {
    expect(formatPct(0)).toBe("+0.00%");
  });
});

describe("scoreColor", () => {
  it("80% 이상이면 emerald을 반환한다", () => {
    expect(scoreColor(90, 100)).toBe("text-emerald-500");
  });

  it("20% 미만이면 red를 반환한다", () => {
    expect(scoreColor(10, 100)).toBe("text-red-500");
  });
});

describe("changeColor", () => {
  it("양수면 positive 색상을 반환한다", () => {
    expect(changeColor(1.5)).toBe("text-positive");
  });

  it("음수면 negative 색상을 반환한다", () => {
    expect(changeColor(-0.5)).toBe("text-negative");
  });

  it("0이면 secondary 색상을 반환한다", () => {
    expect(changeColor(0)).toBe("text-text-secondary");
  });
});

describe("currencySymbol", () => {
  it("KR 코드에 원화 기호를 반환한다", () => {
    expect(currencySymbol("KR")).toBe("₩");
    expect(currencySymbol("005930.KS")).toBe("₩");
    expect(currencySymbol("373220.KQ")).toBe("₩");
  });

  it("기타 코드에 달러 기호를 반환한다", () => {
    expect(currencySymbol("AAPL")).toBe("$");
    expect(currencySymbol("US")).toBe("$");
  });
});

describe("formatPrice", () => {
  it("null을 N/A로 반환한다", () => {
    expect(formatPrice(null, "KR")).toBe("N/A");
  });

  it("KR 종목에 원화 정수 포맷을 반환한다", () => {
    const result = formatPrice(65000, "005930.KS");
    expect(result).toContain("₩");
    expect(result).toContain("65,000");
  });

  it("US 종목에 달러 소수점 포맷을 반환한다", () => {
    const result = formatPrice(150.25, "AAPL");
    expect(result).toContain("$");
    expect(result).toContain("150.25");
  });
});

describe("formatMarketCap", () => {
  it("null을 N/A로 반환한다", () => {
    expect(formatMarketCap(null)).toBe("N/A");
  });

  it("KR 종목에 원화 접두어를 붙인다", () => {
    expect(formatMarketCap(400e12, "KR")).toBe("₩400.0T");
  });

  it("기본값은 달러 접두어를 사용한다", () => {
    expect(formatMarketCap(2.5e9)).toBe("$2.5B");
  });
});
