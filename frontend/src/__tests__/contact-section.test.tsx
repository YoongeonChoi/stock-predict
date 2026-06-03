import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ContactSection from "@/components/ContactSection";
import { ApiError, api } from "@/lib/api";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      submitContact: vi.fn(),
    },
  };
});

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("이름"), { target: { value: "홍길동" } });
  fireEvent.change(screen.getByLabelText("이메일"), { target: { value: "user@example.com" } });
  fireEvent.change(screen.getByLabelText("제목"), { target: { value: "협업 문의" } });
  fireEvent.change(screen.getByLabelText("메시지"), {
    target: { value: "프로젝트 협업 가능 여부를 문의드립니다." },
  });
}

describe("ContactSection", () => {
  afterEach(() => {
    vi.mocked(api.submitContact).mockReset();
  });

  it("contact email link and form labels are rendered", () => {
    render(<ContactSection />);

    expect(screen.getByRole("heading", { name: "Contact" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "contact@yoongeon.xyz" })).toHaveAttribute(
      "href",
      "mailto:contact@yoongeon.xyz",
    );
    expect(screen.getByLabelText("이름")).toBeInTheDocument();
    expect(screen.getByLabelText("이메일")).toBeInTheDocument();
    expect(screen.getByLabelText("제목")).toBeInTheDocument();
    expect(screen.getByLabelText("메시지")).toBeInTheDocument();
  });

  it("blocks invalid email before submitting", async () => {
    render(<ContactSection />);
    fillValidForm();
    fireEvent.change(screen.getByLabelText("이메일"), { target: { value: "invalid" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "문의 보내기" }));
    });

    expect(screen.getAllByText("이메일 형식을 올바르게 입력해 주세요.").length).toBeGreaterThan(0);
    expect(api.submitContact).not.toHaveBeenCalled();
  });

  it("blocks short messages before submitting", async () => {
    render(<ContactSection />);
    fillValidForm();
    fireEvent.change(screen.getByLabelText("메시지"), { target: { value: "짧음" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "문의 보내기" }));
    });

    expect(screen.getAllByText("메시지는 최소 10자 이상 입력해야 합니다.").length).toBeGreaterThan(0);
    expect(api.submitContact).not.toHaveBeenCalled();
  });

  it("shows success message and clears the form after submit", async () => {
    vi.mocked(api.submitContact).mockResolvedValue({
      ok: true,
      message: "문의가 정상적으로 접수되었습니다.",
    });
    render(<ContactSection />);
    fillValidForm();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "문의 보내기" }));
    });

    await waitFor(() => expect(api.submitContact).toHaveBeenCalledTimes(1));
    expect(screen.getByText("문의가 정상적으로 접수되었습니다.")).toBeInTheDocument();
    expect(screen.getByLabelText("이름")).toHaveValue("");
    expect(screen.getByLabelText("이메일")).toHaveValue("");
    expect(screen.getByLabelText("제목")).toHaveValue("");
    expect(screen.getByLabelText("메시지")).toHaveValue("");
  });

  it("shows failure message and preserves form input", async () => {
    vi.mocked(api.submitContact).mockRejectedValue(
      new ApiError(400, {
        error_code: "SP-6018",
        message: "Invalid contact input",
        detail: "메시지는 최소 10자 이상 입력해야 합니다.",
      }),
    );
    render(<ContactSection />);
    fillValidForm();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "문의 보내기" }));
    });

    expect(await screen.findByText("메시지는 최소 10자 이상 입력해야 합니다.")).toBeInTheDocument();
    expect(screen.getByLabelText("이름")).toHaveValue("홍길동");
    expect(screen.getByLabelText("이메일")).toHaveValue("user@example.com");
  });
});
