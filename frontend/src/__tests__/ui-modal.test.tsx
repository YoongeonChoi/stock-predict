import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "@/components/ui";

describe("Modal", () => {
  it("traps keyboard focus and closes on Escape", async () => {
    const handleClose = vi.fn();

    render(
      <Modal onClose={handleClose} open title="테스트 모달">
        <button type="button">첫 번째 작업</button>
        <button type="button">두 번째 작업</button>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog", { name: "테스트 모달" });
    const closeButton = screen.getByRole("button", { name: "닫기" });
    const firstButton = screen.getByRole("button", { name: "첫 번째 작업" });
    const secondButton = screen.getByRole("button", { name: "두 번째 작업" });

    await waitFor(() => expect(closeButton).toHaveFocus());

    secondButton.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(secondButton).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
