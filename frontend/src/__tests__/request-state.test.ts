import { describe, it, expect } from "vitest";
import {
  isConnectionError,
  getConnectionErrorMessage,
  getUserFacingErrorMessage,
} from "@/lib/request-state";
import { ApiError, ApiTimeoutError } from "@/lib/api";

describe("isConnectionError", () => {
  it("Failed to fetch를 감지한다", () => {
    expect(isConnectionError(new Error("Failed to fetch"))).toBe(true);
  });

  it("network request failed를 감지한다", () => {
    expect(isConnectionError(new Error("network request failed"))).toBe(true);
  });

  it("일반 에러는 false를 반환한다", () => {
    expect(isConnectionError(new Error("some error"))).toBe(false);
  });

  it("Error가 아닌 값은 false를 반환한다", () => {
    expect(isConnectionError("string")).toBe(false);
    expect(isConnectionError(null)).toBe(false);
    expect(isConnectionError(42)).toBe(false);
  });
});

describe("getConnectionErrorMessage", () => {
  it("한국어 연결 오류 메시지를 반환한다", () => {
    const message = getConnectionErrorMessage();
    expect(message).toContain("서버");
    expect(message).toContain("연결");
  });
});

describe("getUserFacingErrorMessage", () => {
  it("ApiError의 detail을 우선 반환한다", () => {
    const error = new ApiError(500, { error_code: "SP-5001", message: "내부 오류", detail: "상세 내용" });
    expect(getUserFacingErrorMessage(error, "기본")).toBe("상세 내용");
  });

  it("SP-5018은 timeout 메시지를 반환한다", () => {
    const error = new ApiError(504, { error_code: "SP-5018", message: "timeout" });
    expect(getUserFacingErrorMessage(error, "기본", { timeoutMessage: "시간 초과" })).toBe("시간 초과");
  });

  it("ApiTimeoutError는 timeout 메시지를 반환한다", () => {
    const error = new ApiTimeoutError("timeout");
    expect(getUserFacingErrorMessage(error, "기본", { timeoutMessage: "지연" })).toBe("지연");
  });

  it("연결 오류는 연결 메시지를 반환한다", () => {
    const error = new Error("Failed to fetch");
    const result = getUserFacingErrorMessage(error, "기본");
    expect(result).toContain("서버");
  });

  it("알 수 없는 에러는 fallback을 반환한다", () => {
    expect(getUserFacingErrorMessage(new Error("???"), "대체 메시지")).toBe("대체 메시지");
  });

  it("includeCode 옵션이 에러 코드를 포함한다", () => {
    const error = new ApiError(400, { error_code: "SP-6001", message: "잘못된 요청" });
    const result = getUserFacingErrorMessage(error, "기본", { includeCode: true });
    expect(result).toContain("SP-6001");
  });
});
