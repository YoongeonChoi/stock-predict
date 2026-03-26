"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import AuthSupportPanel from "@/components/auth/AuthSupportPanel";
import PasswordStrengthChecklist from "@/components/auth/PasswordStrengthChecklist";
import { useAuth } from "@/components/AuthProvider";
import PageHeader from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import {
  describeAuthErrorMessage,
  formatPhoneNumber,
  getPasswordStrength,
  isValidBirthDate,
  isValidFullName,
  isValidPhoneNumber,
  isValidUsername,
  normalizeFullName,
  normalizePhoneNumber,
  normalizeUsername,
} from "@/lib/account";
import { api } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

type AuthMode = "signin" | "signup";

interface SignUpFormState {
  username: string;
  email: string;
  fullName: string;
  phoneNumber: string;
  birthDate: string;
  password: string;
  passwordConfirm: string;
}

interface UsernameCheckState {
  checkedValue: string;
  available: boolean;
  valid: boolean;
  message: string;
  checking: boolean;
}

const EMPTY_SIGNUP_FORM: SignUpFormState = {
  username: "",
  email: "",
  fullName: "",
  phoneNumber: "",
  birthDate: "",
  password: "",
  passwordConfirm: "",
};

function FormField({
  label,
  children,
  helper,
}: {
  label: string;
  children: ReactNode;
  helper?: string;
}) {
  return (
    <div>
      <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">{label}</label>
      {children}
      {helper ? <div className="mt-2 text-xs text-text-secondary">{helper}</div> : null}
    </div>
  );
}

function AuthPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { configured, loading, session, refreshProfile } = useAuth();

  const [mode, setMode] = useState<AuthMode>(searchParams.get("mode") === "signup" ? "signup" : "signin");
  const [signinEmail, setSigninEmail] = useState("");
  const [signinPassword, setSigninPassword] = useState("");
  const [signup, setSignup] = useState<SignUpFormState>(EMPTY_SIGNUP_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [usernameState, setUsernameState] = useState<UsernameCheckState>({
    checkedValue: "",
    available: false,
    valid: false,
    message: "아이디를 입력하고 중복 확인을 진행해 주세요.",
    checking: false,
  });

  const nextPath = searchParams.get("next") || "/portfolio";

  useEffect(() => {
    if (!loading && session) {
      router.replace(nextPath);
    }
  }, [loading, nextPath, router, session]);

  const passwordStrength = useMemo(
    () => getPasswordStrength(signup.password, signup.passwordConfirm),
    [signup.password, signup.passwordConfirm],
  );

  const normalizedUsername = normalizeUsername(signup.username);
  const usernameValidated = Boolean(
    normalizedUsername &&
    usernameState.checkedValue === normalizedUsername &&
    usernameState.valid &&
    usernameState.available,
  );

  const signUpReady = Boolean(
    configured &&
    signup.email.trim() &&
    isValidUsername(signup.username) &&
    isValidFullName(signup.fullName) &&
    isValidPhoneNumber(signup.phoneNumber) &&
    isValidBirthDate(signup.birthDate) &&
    passwordStrength.checks.minLength &&
    passwordStrength.checks.uppercase &&
    passwordStrength.checks.lowercase &&
    passwordStrength.checks.number &&
    passwordStrength.checks.symbol &&
    passwordStrength.checks.match &&
    usernameValidated,
  );

  const updateSignupField = <K extends keyof SignUpFormState>(key: K, value: SignUpFormState[K]) => {
    setSignup((prev) => ({ ...prev, [key]: value }));
    if (key === "username") {
      setUsernameState((prev) => ({
        ...prev,
        valid: false,
        available: false,
        message: "아이디가 변경되었습니다. 다시 중복 확인해 주세요.",
      }));
    }
  };

  const handleUsernameCheck = async () => {
    if (!isValidUsername(signup.username)) {
      setUsernameState({
        checkedValue: normalizedUsername,
        valid: false,
        available: false,
        message: "아이디는 영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 4~20자까지 사용할 수 있습니다.",
        checking: false,
      });
      return;
    }

    setUsernameState((prev) => ({ ...prev, checking: true }));
    try {
      const result = await api.checkUsernameAvailability(signup.username);
      setUsernameState({
        checkedValue: result.normalized_username,
        valid: result.valid,
        available: result.available,
        message: result.message,
        checking: false,
      });
    } catch {
      setUsernameState({
        checkedValue: normalizedUsername,
        valid: false,
        available: false,
        message: "중복 확인 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        checking: false,
      });
    }
  };

  const handleSubmit = async () => {
    const client = getSupabaseBrowserClient();
    if (!configured || !client) {
      toast("Supabase 설정이 비어 있어 로그인 화면을 열 수 없습니다.", "error");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "signup") {
        if (!signUpReady) {
          toast("회원가입 필수 입력과 보안 조건을 모두 확인해 주세요.", "error");
          return;
        }

        const redirectTo = `${window.location.origin}${nextPath}`;
        const { data, error } = await client.auth.signUp({
          email: signup.email.trim(),
          password: signup.password,
          options: {
            emailRedirectTo: redirectTo,
            data: {
              username: normalizedUsername,
              full_name: signup.fullName.trim(),
              phone_number: normalizePhoneNumber(signup.phoneNumber),
              birth_date: signup.birthDate,
            },
          },
        });

        if (error) {
          throw error;
        }

        if (data.session) {
          await refreshProfile();
          toast("회원가입과 로그인이 완료되었습니다.", "success");
          router.replace(nextPath);
        } else {
          toast("가입 확인 메일을 보냈습니다. 인증 링크를 눌러 계정을 활성화해 주세요.", "info");
          setMode("signin");
          setSigninEmail(signup.email.trim());
          setSignup(EMPTY_SIGNUP_FORM);
        }
        return;
      }

      if (!signinEmail.trim() || !signinPassword) {
        toast("이메일과 비밀번호를 모두 입력해 주세요.", "error");
        return;
      }

      const { error } = await client.auth.signInWithPassword({
        email: signinEmail.trim(),
        password: signinPassword,
      });
      if (error) {
        throw error;
      }

      await refreshProfile();
      toast("로그인되었습니다.", "success");
      router.replace(nextPath);
    } catch (error) {
      toast(describeAuthErrorMessage(error, "인증 처리 중 문제가 발생했습니다."), "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-shell space-y-5">
      <PageHeader
        eyebrow="계정"
        title="로그인 및 회원가입"
        description="보유 종목, 추천 결과, 자산 기준을 계정별로 안전하게 분리하려면 먼저 로그인부터 연결해 주세요."
        meta={<span className="info-chip">로그인 후 이동: {nextPath}</span>}
      />

      <section className="mx-auto grid max-w-[1180px] gap-5 xl:grid-cols-[minmax(0,1.12fr)_360px]">
        <div className="card !p-5 space-y-5">
          <div className="flex gap-2 rounded-2xl border border-border/70 bg-surface/50 p-1">
            <button
              onClick={() => setMode("signin")}
              className={`flex-1 rounded-2xl px-4 py-2.5 text-sm font-semibold transition-colors ${mode === "signin" ? "bg-accent text-white" : "text-text-secondary"}`}
            >
              로그인
            </button>
            <button
              onClick={() => setMode("signup")}
              className={`flex-1 rounded-2xl px-4 py-2.5 text-sm font-semibold transition-colors ${mode === "signup" ? "bg-accent text-white" : "text-text-secondary"}`}
            >
              회원가입
            </button>
          </div>

          {mode === "signin" ? (
            <div className="space-y-4">
              <FormField label="이메일">
                <input
                  value={signinEmail}
                  onChange={(event) => setSigninEmail(event.target.value)}
                  type="email"
                  autoComplete="email"
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="you@example.com"
                />
              </FormField>
              <FormField label="비밀번호">
                <input
                  value={signinPassword}
                  onChange={(event) => setSigninPassword(event.target.value)}
                  type="password"
                  autoComplete="current-password"
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="비밀번호 입력"
                />
              </FormField>
            </div>
          ) : (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  label="아이디"
                  helper="영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 사용할 수 있습니다. 입력 중 자동으로 소문자로 정리됩니다."
                >
                  <div className="flex gap-2">
                    <input
                      value={signup.username}
                      onChange={(event) =>
                        updateSignupField(
                          "username",
                          normalizeUsername(event.target.value.replace(/\s+/g, "")).slice(0, 20),
                        )
                      }
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      maxLength={20}
                      className="min-w-0 flex-1 rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                      placeholder="alpha_user"
                    />
                    <button
                      type="button"
                      onClick={handleUsernameCheck}
                      disabled={usernameState.checking}
                      className="action-chip-secondary shrink-0"
                    >
                      {usernameState.checking ? "확인 중..." : "중복 확인"}
                    </button>
                  </div>
                </FormField>
                <FormField label="이메일">
                  <input
                    value={signup.email}
                    onChange={(event) => updateSignupField("email", event.target.value)}
                    type="email"
                    autoComplete="email"
                    autoCapitalize="none"
                    spellCheck={false}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                    placeholder="you@example.com"
                  />
                </FormField>
                <FormField label="이름">
                  <input
                    value={signup.fullName}
                    onChange={(event) => updateSignupField("fullName", normalizeFullName(event.target.value).slice(0, 40))}
                    autoComplete="name"
                    maxLength={40}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                    placeholder="홍길동"
                  />
                </FormField>
                <FormField label="전화번호" helper="하이픈 없이 입력해도 자동으로 읽기 좋은 형식으로 정리됩니다.">
                  <input
                    value={signup.phoneNumber}
                    onChange={(event) => updateSignupField("phoneNumber", formatPhoneNumber(event.target.value))}
                    inputMode="numeric"
                    autoComplete="tel"
                    maxLength={15}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                    placeholder="010-1234-5678"
                  />
                </FormField>
                <FormField label="생년월일">
                  <input
                    value={signup.birthDate}
                    onChange={(event) => updateSignupField("birthDate", event.target.value)}
                    type="date"
                    autoComplete="bday"
                    max={new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  />
                </FormField>
                <div className="rounded-[22px] border border-border/70 bg-surface/45 px-4 py-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">가입 체크</div>
                  <ul className="mt-3 space-y-2 text-sm text-text-secondary">
                    <li>{isValidFullName(signup.fullName) ? "이름 형식이 확인되었습니다." : "이름은 2자 이상으로 입력해 주세요."}</li>
                    <li>{isValidPhoneNumber(signup.phoneNumber) ? "전화번호 형식이 확인되었습니다." : "전화번호를 올바르게 입력해 주세요."}</li>
                    <li>{isValidBirthDate(signup.birthDate) ? "생년월일 형식이 확인되었습니다." : "생년월일을 선택해 주세요."}</li>
                    <li className={usernameValidated ? "text-positive" : ""}>{usernameState.message}</li>
                  </ul>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="비밀번호">
                  <input
                    value={signup.password}
                    onChange={(event) => updateSignupField("password", event.target.value)}
                    type="password"
                    autoComplete="new-password"
                    maxLength={128}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                    placeholder="강한 비밀번호 입력"
                  />
                </FormField>
                <FormField label="비밀번호 재확인">
                  <input
                    value={signup.passwordConfirm}
                    onChange={(event) => updateSignupField("passwordConfirm", event.target.value)}
                    type="password"
                    autoComplete="new-password"
                    maxLength={128}
                    className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                    placeholder="비밀번호 다시 입력"
                  />
                </FormField>
              </div>

              <PasswordStrengthChecklist result={passwordStrength} />
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={submitting || loading || (mode === "signup" && !signUpReady)}
            className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "처리 중..." : mode === "signup" ? "회원가입하고 계속하기" : "로그인하고 계속하기"}
          </button>

          {!configured ? (
            <div className="rounded-2xl border border-negative/20 bg-negative/5 px-4 py-3 text-sm text-negative">
              Supabase 브라우저 설정이 비어 있습니다. `NEXT_PUBLIC_SUPABASE_URL`과 `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`를 확인해 주세요.
            </div>
          ) : null}
        </div>

        <AuthSupportPanel />
      </section>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<div className="page-shell animate-pulse"><div className="card h-64" /></div>}>
      <AuthPageContent />
    </Suspense>
  );
}
