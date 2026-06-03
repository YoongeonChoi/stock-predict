import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LandingPage from "@/app/page";

describe("LandingPage", () => {
  it("renders the public landing hero and dashboard CTA", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        name: "시장 신호를 읽고, 포트폴리오 판단까지 이어갑니다.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /대시보드/ })[0]).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "기회 레이더 보기" })).toHaveAttribute("href", "/radar");
  });

  it("keeps the required landing sections visible", () => {
    render(<LandingPage />);

    expect(screen.getByRole("heading", { name: "필요한 화면만 남깁니다." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "데이터에서 행동까지 짧게." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "좋은 판단은 한계를 같이 봅니다." })).toBeInTheDocument();
    expect(screen.getByText("수익 보장 없음")).toBeInTheDocument();
  });
});
