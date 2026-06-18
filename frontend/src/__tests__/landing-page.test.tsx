import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LandingPage from "@/app/page";

describe("LandingPage", () => {
  it("renders the public landing hero and dashboard CTA", () => {
    render(<LandingPage />);

    expect(
      screen.getByRole("heading", {
        name: "SP",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /대시보드/ })[0]).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "기회 레이더 보기" })).toHaveAttribute("href", "/radar");
  });

  it("keeps the required landing sections visible", () => {
    render(<LandingPage />);

    expect(screen.getByRole("heading", { name: "주요 화면" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "분석 순서" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "운영 기준" })).toBeInTheDocument();
    expect(screen.getByText("수익 보장 없음")).toBeInTheDocument();
  });
});
