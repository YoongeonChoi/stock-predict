import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "@/components/Toast";

function TestTrigger({ type = "success" as "success" | "error" | "info" }) {
  const { toast } = useToast();
  return (
    <button onClick={() => toast("테스트 메시지", type)}>
      트리거
    </button>
  );
}

describe("Toast", () => {
  it("성공 토스트에 role=status를 사용한다", async () => {
    render(
      <ToastProvider>
        <TestTrigger type="success" />
      </ToastProvider>,
    );

    await act(async () => {
      screen.getByText("트리거").click();
    });

    const toast = screen.getByText("테스트 메시지");
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute("role", "status");
  });

  it("에러 토스트에 role=alert를 사용한다", async () => {
    render(
      <ToastProvider>
        <TestTrigger type="error" />
      </ToastProvider>,
    );

    await act(async () => {
      screen.getByText("트리거").click();
    });

    const toast = screen.getByText("테스트 메시지");
    expect(toast).toHaveAttribute("role", "alert");
  });

  it("토스트 컨테이너에 aria-live가 설정되어 있다", async () => {
    const { container } = render(
      <ToastProvider>
        <TestTrigger />
      </ToastProvider>,
    );

    const liveRegion = container.querySelector("[aria-live]");
    expect(liveRegion).toBeInTheDocument();
  });
});
