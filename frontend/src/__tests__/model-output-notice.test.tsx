import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ModelOutputNotice from "@/components/ModelOutputNotice";

describe("ModelOutputNotice", () => {
  it("추천 출력이 매수 지시나 수익 보장이 아님을 고지한다", () => {
    render(<ModelOutputNotice />);

    expect(screen.getByText(/조건부 분포/)).toBeInTheDocument();
    expect(screen.getByText(/수익 보장이나 즉시 매수 지시가 아니며/)).toBeInTheDocument();
    expect(screen.getByText(/예측 연구실의 검증 표본/)).toBeInTheDocument();
  });
});
