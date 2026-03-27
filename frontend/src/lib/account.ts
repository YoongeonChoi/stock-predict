import type { User } from "@supabase/supabase-js";

import { ApiError } from "@/lib/api";

export interface AccountProfileShape {
  user_id?: string;
  email?: string | null;
  pending_email?: string | null;
  email_verified?: boolean;
  email_confirmed_at?: string | null;
  email_change_sent_at?: string | null;
  username?: string | null;
  full_name?: string | null;
  phone_number?: string | null;
  phone_masked?: string | null;
  birth_date?: string | null;
}

export interface PasswordRequirementStatus {
  minLength: boolean;
  uppercase: boolean;
  lowercase: boolean;
  number: boolean;
  symbol: boolean;
  match: boolean;
}

export interface PasswordStrengthResult {
  score: number;
  label: "매우 약함" | "약함" | "보통" | "좋음" | "강함";
  checks: PasswordRequirementStatus;
}

const USERNAME_PATTERN = /^[a-z][a-z0-9_]{3,19}$/;
const PHONE_PATTERN = /^\d{9,15}$/;
const FULL_NAME_PATTERN = /^[A-Za-z가-힣\s]{2,40}$/;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SYMBOL_PATTERN = /[^A-Za-z0-9]/;

function readMetadataValue(metadata: unknown, keys: string[]): string | null {
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  for (const key of keys) {
    const value = (metadata as Record<string, unknown>)[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

export function normalizeUsername(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidUsername(value: string): boolean {
  return USERNAME_PATTERN.test(value.trim());
}

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(normalizeEmail(value));
}

export function normalizeFullName(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function isValidFullName(value: string): boolean {
  const normalized = normalizeFullName(value);
  return FULL_NAME_PATTERN.test(normalized);
}

export function normalizePhoneNumber(value: string): string {
  return value.replace(/\D/g, "");
}

export function formatPhoneNumber(value: string): string {
  const digits = normalizePhoneNumber(value).slice(0, 15);
  if (digits.length <= 3) {
    return digits;
  }
  if (digits.length <= 7) {
    return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  }
  if (digits.length <= 11) {
    const middleLength = digits.length === 10 ? 3 : 4;
    return `${digits.slice(0, 3)}-${digits.slice(3, 3 + middleLength)}-${digits.slice(3 + middleLength)}`;
  }
  return digits;
}

export function isValidPhoneNumber(value: string): boolean {
  return PHONE_PATTERN.test(normalizePhoneNumber(value));
}

export function isValidBirthDate(value: string): boolean {
  if (!value) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return false;
  }
  const today = new Date();
  const lower = new Date("1900-01-01T00:00:00");
  return parsed >= lower && parsed < new Date(today.toDateString());
}

export function getPasswordStrength(password: string, confirmation = ""): PasswordStrengthResult {
  const checks: PasswordRequirementStatus = {
    minLength: password.length >= 10,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /\d/.test(password),
    symbol: SYMBOL_PATTERN.test(password),
    match: Boolean(password) && password === confirmation,
  };

  const baseScore = [
    checks.minLength,
    checks.uppercase,
    checks.lowercase,
    checks.number,
    checks.symbol,
  ].filter(Boolean).length;

  const score = Math.min(4, Math.max(0, baseScore - 1 + (password.length >= 14 ? 1 : 0)));
  const label =
    score <= 0 ? "매우 약함" :
    score === 1 ? "약함" :
    score === 2 ? "보통" :
    score === 3 ? "좋음" :
    "강함";

  return { score, label, checks };
}

export function describeAuthErrorMessage(error: unknown, fallback: string): string {
  const errorCode =
    error && typeof error === "object" && "code" in error
      ? String((error as { code?: unknown }).code ?? "")
      : "";
  if (error instanceof ApiError && error.errorCode === "SP-6016") {
    return error.detail || "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  }
  const message = error instanceof Error ? error.message : fallback;
  const lowered = `${errorCode} ${message}`.toLowerCase();
  if (
    lowered.includes("reauthentication_needed") ||
    lowered.includes("reauthentication_not_valid") ||
    lowered.includes("reauth_nonce_missing")
  ) {
    return "비밀번호 변경 전에 보안 확인 코드를 먼저 요청하고, 메일로 받은 코드를 입력해 주세요.";
  }
  if (message.toLowerCase().includes("email not confirmed")) {
    return "이메일 인증이 아직 완료되지 않았습니다. 받은 편지함에서 인증 링크를 확인해 주세요.";
  }
  if (message.toLowerCase().includes("invalid login credentials")) {
    return "이메일 또는 비밀번호가 올바르지 않습니다.";
  }
  if (message.toLowerCase().includes("user already registered")) {
    return "이미 가입된 이메일입니다. 로그인하거나 비밀번호 재설정을 이용해 주세요.";
  }
  if (message.toLowerCase().includes("password should be at least")) {
    return "비밀번호 보안 조건을 다시 확인해 주세요.";
  }
  return message || fallback;
}

export function requiresPasswordReauthentication(error: unknown): boolean {
  const errorCode =
    error && typeof error === "object" && "code" in error
      ? String((error as { code?: unknown }).code ?? "")
      : "";
  const message = error instanceof Error ? error.message : String(error ?? "");
  const lowered = `${errorCode} ${message}`.toLowerCase();
  return (
    lowered.includes("reauthentication_needed") ||
    lowered.includes("reauthentication_not_valid") ||
    lowered.includes("reauth_nonce_missing")
  );
}

export function extractAccountProfileFromUser(user: User | null): AccountProfileShape | null {
  if (!user) {
    return null;
  }
  const metadata = user.user_metadata ?? user.identities?.[0]?.identity_data ?? {};
  const phoneNumber = readMetadataValue(metadata, ["phone_number", "phone"]);
  const username = readMetadataValue(metadata, ["username"]);
  const emailConfirmedAt = user.email_confirmed_at ?? null;

  return {
    user_id: user.id,
    email: user.email ?? null,
    pending_email: user.new_email ?? null,
    email_verified: Boolean(emailConfirmedAt),
    email_confirmed_at: emailConfirmedAt,
    email_change_sent_at: user.email_change_sent_at ?? null,
    username: username ? normalizeUsername(username) : null,
    full_name: readMetadataValue(metadata, ["full_name", "name"]),
    phone_number: phoneNumber ? formatPhoneNumber(phoneNumber) : null,
    phone_masked: phoneNumber
      ? formatPhoneNumber(phoneNumber).replace(/-(\d{3,4})-/, "-****-")
      : null,
    birth_date: readMetadataValue(metadata, ["birth_date"]),
  };
}
