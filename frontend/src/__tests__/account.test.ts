import { describe, it, expect } from "vitest";
import {
  normalizeUsername,
  isValidUsername,
  isValidEmail,
  isValidPhoneNumber,
  isValidFullName,
  getPasswordStrength,
} from "@/lib/account";

describe("normalizeUsername", () => {
  it("소문자로 변환하고 양끝 공백을 제거한다", () => {
    expect(normalizeUsername("  MyUser  ")).toBe("myuser");
  });
});

describe("isValidUsername", () => {
  it("영문 소문자 시작 4~20자를 허용한다", () => {
    expect(isValidUsername("user1")).toBe(true);
    expect(isValidUsername("a_b_c_d")).toBe(true);
    expect(isValidUsername("abcdefghijklmnopqrst")).toBe(true);
  });

  it("숫자 시작을 거부한다", () => {
    expect(isValidUsername("1user")).toBe(false);
  });

  it("대문자를 거부한다", () => {
    expect(isValidUsername("User1")).toBe(false);
  });

  it("3자 이하를 거부한다", () => {
    expect(isValidUsername("abc")).toBe(false);
  });

  it("21자 이상을 거부한다", () => {
    expect(isValidUsername("a".repeat(21))).toBe(false);
  });

  it("특수문자(밑줄 제외)를 거부한다", () => {
    expect(isValidUsername("user-name")).toBe(false);
    expect(isValidUsername("user.name")).toBe(false);
  });
});

describe("isValidEmail", () => {
  it("표준 이메일을 허용한다", () => {
    expect(isValidEmail("test@example.com")).toBe(true);
  });

  it("@ 없는 문자열을 거부한다", () => {
    expect(isValidEmail("invalid")).toBe(false);
  });

  it("빈 문자열을 거부한다", () => {
    expect(isValidEmail("")).toBe(false);
  });
});

describe("isValidPhoneNumber", () => {
  it("9~15자리 숫자를 허용한다", () => {
    expect(isValidPhoneNumber("01012345678")).toBe(true);
    expect(isValidPhoneNumber("123456789")).toBe(true);
  });

  it("하이픈 포함 번호를 정규화 후 허용한다", () => {
    expect(isValidPhoneNumber("010-1234-5678")).toBe(true);
  });

  it("8자리 이하를 거부한다", () => {
    expect(isValidPhoneNumber("12345678")).toBe(false);
  });
});

describe("isValidFullName", () => {
  it("한글 이름을 허용한다", () => {
    expect(isValidFullName("홍길동")).toBe(true);
  });

  it("영문 이름을 허용한다", () => {
    expect(isValidFullName("John Doe")).toBe(true);
  });

  it("1자를 거부한다", () => {
    expect(isValidFullName("홍")).toBe(false);
  });

  it("숫자 포함 이름을 거부한다", () => {
    expect(isValidFullName("홍길동123")).toBe(false);
  });
});

describe("getPasswordStrength", () => {
  it("모든 조건 충족 시 강함을 반환한다", () => {
    const result = getPasswordStrength("Str0ng!Pass", "Str0ng!Pass");
    expect(result.label).toBe("강함");
    expect(result.checks.minLength).toBe(true);
    expect(result.checks.uppercase).toBe(true);
    expect(result.checks.lowercase).toBe(true);
    expect(result.checks.number).toBe(true);
    expect(result.checks.symbol).toBe(true);
    expect(result.checks.match).toBe(true);
  });

  it("짧은 비밀번호는 매우 약함을 반환한다", () => {
    const result = getPasswordStrength("abc", "abc");
    expect(result.label).toBe("매우 약함");
    expect(result.checks.minLength).toBe(false);
  });

  it("확인 불일치를 감지한다", () => {
    const result = getPasswordStrength("Str0ng!Pass", "different");
    expect(result.checks.match).toBe(false);
  });
});
