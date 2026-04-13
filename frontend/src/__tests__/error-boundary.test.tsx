import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import GlobalError from "@/app/error";
import GlobalLoading from "@/app/loading";

describe("GlobalError", () => {
  it("에러 메시지와 다시 시도 버튼을 렌더링한다", () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error("test")} reset={reset} />);

    expect(screen.getByText("페이지를 불러오는 중 문제가 발생했습니다")).toBeInTheDocument();
    expect(screen.getByText("다시 시도")).toBeInTheDocument();
  });

  it("다시 시도 버튼이 reset을 호출한다", () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error("test")} reset={reset} />);

    fireEvent.click(screen.getByText("다시 시도"));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});

describe("GlobalLoading", () => {
  it("불러오는 중 텍스트를 렌더링한다", () => {
    render(<GlobalLoading />);
    expect(screen.getByText("불러오는 중")).toBeInTheDocument();
  });

  it("aria-busy 속성이 설정되어 있다", () => {
    render(<GlobalLoading />);
    const container = screen.getByRole("status");
    expect(container).toHaveAttribute("aria-busy", "true");
  });
});
