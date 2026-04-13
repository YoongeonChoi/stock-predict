import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SectorRotationBoard from "@/components/SectorRotationBoard";

const MOCK_DATA = [
  { sector: "반도체", ticker: "005930.KS", price: 65000, change_pct: 2.5, breadth: 8, leader_name: "삼성전자" },
  { sector: "자동차", ticker: "005380.KS", price: 220000, change_pct: 1.2, breadth: 5, leader_name: "현대자동차" },
  { sector: "바이오", ticker: "207940.KS", price: 720000, change_pct: -1.8, breadth: 6, leader_name: "삼성바이오로직스" },
  { sector: "금융", ticker: "105560.KS", price: 65000, change_pct: -0.3, breadth: 7, leader_name: "KB금융" },
];

describe("SectorRotationBoard", () => {
  it("null 데이터면 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<SectorRotationBoard data={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("빈 배열이면 아무것도 렌더링하지 않는다", () => {
    const { container } = render(<SectorRotationBoard data={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("섹터 이름과 대장주를 렌더링한다", () => {
    render(<SectorRotationBoard data={MOCK_DATA} />);
    expect(screen.getAllByText("반도체").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
    expect(screen.getByText("자동차")).toBeInTheDocument();
    expect(screen.getByText("바이오")).toBeInTheDocument();
  });

  it("섹터 로테이션 제목을 표시한다", () => {
    render(<SectorRotationBoard data={MOCK_DATA} />);
    expect(screen.getByText("섹터 로테이션")).toBeInTheDocument();
  });

  it("상승/하락 섹터 수를 올바르게 표시한다", () => {
    render(<SectorRotationBoard data={MOCK_DATA} />);
    const allTwos = screen.getAllByText("2");
    expect(allTwos.length).toBeGreaterThanOrEqual(1);
  });

  it("등락률을 포맷해서 표시한다", () => {
    render(<SectorRotationBoard data={MOCK_DATA} />);
    expect(screen.getAllByText("+2.50%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("-1.80%")).toBeInTheDocument();
  });

  it("대장주 링크가 종목 상세 페이지로 연결된다", () => {
    render(<SectorRotationBoard data={MOCK_DATA} />);
    const link = screen.getByText("삼성전자");
    expect(link.closest("a")).toHaveAttribute("href", "/stock/005930.KS");
  });
});
