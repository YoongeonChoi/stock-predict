"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import AuthSupportPanel from "@/components/auth/AuthSupportPanel";
import PasswordStrengthChecklist from "@/components/auth/PasswordStrengthChecklist";
import { useAuth } from "@/components/AuthProvider";
import PageHeader from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { useCooldownTimer } from "@/hooks/useCooldownTimer";
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
import { api, getApiRetryAfterSeconds, isApiErrorCode } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";
import { cn } from "@/lib/utils";

type AuthMode = "signin" | "signup" | "recovery";

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

function resolveMode(rawMode: string | null): AuthMode {
  if (rawMode === "signup") {
    return "signup";
  }
  if (rawMode === "recovery") {
    return "recovery";
  }
  return "signin";
}

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
      <label className="ui-field-label">{label}</label>
      {children}
      {helper ? <div className="ui-helper-text">{helper}</div> : null}
    </div>
  );
}

function AuthPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { configured, loading, session, refreshProfile } = useAuth();

  const nextParam = searchParams.get("next");
  const nextPath = nextParam && nextParam.startsWith("/") ? nextParam : "/portfolio";
  const modeFromParams = useMemo(() => resolveMode(searchParams.get("mode")), [searchParams]);

  const [mode, setMode] = useState<AuthMode>(modeFromParams);
  const [signinEmail, setSigninEmail] = useState("");
  const [signinPassword, setSigninPassword] = useState("");
  const [signup, setSignup] = useState<SignUpFormState>(EMPTY_SIGNUP_FORM);
  const [recoveryPassword, setRecoveryPassword] = useState("");
  const [recoveryConfirm, setRecoveryConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [supportAction, setSupportAction] = useState<"verification" | "reset" | null>(null);
  const [usernameState, setUsernameState] = useState<UsernameCheckState>({
    checkedValue: "",
    available: false,
    valid: false,
    message: "아이디를 입력하고 중복 확인을 진행해 주세요.",
    checking: false,
  });
  const usernameCooldown = useCooldownTimer();
  const signupCooldown = useCooldownTimer();
  const verificationCooldown = useCooldownTimer();
  const resetCooldown = useCooldownTimer();

  useEffect(() => {
    setMode(modeFromParams);
  }, [modeFromParams]);

  useEffect(() => {
    if (!loading && session && mode !== "recovery") {
      router.replace(nextPath);
    }
  }, [loading, mode, nextPath, router, session]);

  const setModeInUrl = (nextMode: AuthMode) => {
    const params = new URLSearchParams(searchParams.toString());
    if (nextMode === "signin") {
      params.delete("mode");
    } else {
      params.set("mode", nextMode);
    }
    if (nextPath) {
      params.set("next", nextPath);
    }
    const suffix = params.toString() ? `?${params.toString()}` : "";
    setMode(nextMode);
    router.replace(`/auth${suffix}`);
  };

  const passwordStrength = useMemo(
    () => getPasswordStrength(signup.password, signup.passwordConfirm),
    [signup.password, signup.passwordConfirm],
  );
  const recoveryStrength = useMemo(
    () => getPasswordStrength(recoveryPassword, recoveryConfirm),
    [recoveryPassword, recoveryConfirm],
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

  const recoveryReady = Boolean(
    session &&
    recoveryStrength.checks.minLength &&
    recoveryStrength.checks.uppercase &&
    recoveryStrength.checks.lowercase &&
    recoveryStrength.checks.number &&
    recoveryStrength.checks.symbol &&
    recoveryStrength.checks.match,
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
    if (usernameCooldown.active) {
      setUsernameState((prev) => ({
        ...prev,
        checking: false,
        message: `중복 확인 요청이 많아 ${usernameCooldown.seconds}초 후 다시 시도해 주세요.`,
      }));
      return;
    }

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
    } catch (error) {
      if (isApiErrorCode(error, "SP-6016")) {
        const retryAfter = getApiRetryAfterSeconds(error) ?? 30;
        usernameCooldown.start(retryAfter);
        setUsernameState({
          checkedValue: normalizedUsername,
          valid: false,
          available: false,
          message: error.detail || `중복 확인 요청이 많아 ${retryAfter}초 후 다시 시도해 주세요.`,
          checking: false,
        });
        return;
      }
      setUsernameState({
        checkedValue: normalizedUsername,
        valid: false,
        available: false,
        message: "중복 확인 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        checking: false,
      });
    }
  };

  const handleResendVerification = async () => {
    const client = getSupabaseBrowserClient();
    if (!configured || !client) {
      toast("Supabase 설정이 비어 있어 인증 메일을 보낼 수 없습니다.", "error");
      return;
    }
    if (verificationCooldown.active) {
      toast(`인증 메일은 ${verificationCooldown.seconds}초 후 다시 보낼 수 있습니다.`, "error");
      return;
    }
    if (!signinEmail.trim()) {
      toast("인증 메일을 보낼 이메일을 먼저 입력해 주세요.", "error");
      return;
    }

    setSupportAction("verification");
    try {
      const { error } = await client.auth.resend({
        type: "signup",
        email: signinEmail.trim(),
        options: {
          emailRedirectTo: `${window.location.origin}${nextPath}`,
        },
      });
      if (error) {
        throw error;
      }
      verificationCooldown.start(60);
      toast("가입 확인 메일을 다시 보냈습니다. 받은 편지함을 확인해 주세요.", "success");
    } catch (error) {
      toast(describeAuthErrorMessage(error, "인증 메일 재전송 중 문제가 발생했습니다."), "error");
    } finally {
      setSupportAction(null);
    }
  };

  const handlePasswordResetRequest = async () => {
    const client = getSupabaseBrowserClient();
    if (!configured || !client) {
      toast("Supabase 설정이 비어 있어 재설정 메일을 보낼 수 없습니다.", "error");
      return;
    }
    if (resetCooldown.active) {
      toast(`재설정 메일은 ${resetCooldown.seconds}초 후 다시 요청할 수 있습니다.`, "error");
      return;
    }
    if (!signinEmail.trim()) {
      toast("비밀번호 재설정 메일을 보낼 이메일을 먼저 입력해 주세요.", "error");
      return;
    }

    setSupportAction("reset");
    try {
      const { error } = await client.auth.resetPasswordForEmail(signinEmail.trim(), {
        redirectTo: `${window.location.origin}/auth?mode=recovery&next=${encodeURIComponent(nextPath)}`,
      });
      if (error) {
        throw error;
      }
      resetCooldown.start(60);
      toast("비밀번호 재설정 메일을 보냈습니다. 메일의 링크에서 새 비밀번호를 설정해 주세요.", "success");
    } catch (error) {
      toast(describeAuthErrorMessage(error, "비밀번호 재설정 메일 전송 중 문제가 발생했습니다."), "error");
    } finally {
      setSupportAction(null);
    }
  };

  const handleAuthSubmit = async () => {
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
        if (signupCooldown.active) {
          toast(`회원가입 검증 요청이 많아 ${signupCooldown.seconds}초 후 다시 시도해 주세요.`, "error");
          return;
        }

        const validation = await api.validateSignup({
          username: signup.username,
          email: signup.email,
          full_name: signup.fullName,
          phone_number: signup.phoneNumber,
          birth_date: signup.birthDate,
          password: signup.password,
          password_confirm: signup.passwordConfirm,
        });
        const redirectTo = `${window.location.origin}${nextPath}`;
        const { data, error } = await client.auth.signUp({
          email: validation.email,
          password: signup.password,
          options: {
            emailRedirectTo: redirectTo,
            data: {
              username: validation.normalized_username,
              full_name: validation.normalized_full_name,
              phone_number: validation.normalized_phone_number,
              birth_date: validation.birth_date,
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
          setSigninEmail(validation.email);
          setSignup(EMPTY_SIGNUP_FORM);
          setModeInUrl("signin");
        }
        return;
      }

      if (mode === "recovery") {
        if (!session) {
          toast("복구 세션이 확인되지 않습니다. 비밀번호 재설정 메일을 다시 요청해 주세요.", "error");
          return;
        }
        if (!recoveryReady) {
          toast("새 비밀번호 보안 조건을 모두 충족해 주세요.", "error");
          return;
        }

        const { error } = await client.auth.updateUser({ password: recoveryPassword });
        if (error) {
          throw error;
        }

        await refreshProfile();
        toast("새 비밀번호가 저장되었습니다.", "success");
        setRecoveryPassword("");
        setRecoveryConfirm("");
        router.replace(nextPath);
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
      if (mode === "signup" && isApiErrorCode(error, "SP-6016")) {
        const retryAfter = getApiRetryAfterSeconds(error) ?? 30;
        signupCooldown.start(retryAfter);
      }
      toast(describeAuthErrorMessage(error, "인증 처리 중 문제가 발생했습니다."), "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-shell space-y-5">
      <PageHeader
        variant="compact"
        eyebrow="계정"
        title={mode === "recovery" ? "비밀번호 재설정" : "로그인 및 회원가입"}
        description={
          mode === "recovery"
            ? "복구 링크를 통해 들어왔다면 새 비밀번호를 바로 설정할 수 있습니다."
            : "보유 종목, 추천 결과, 자산 기준을 계정별로 안전하게 분리하려면 먼저 로그인부터 연결해 주세요."
        }
        meta={<span className="info-chip">로그인 후 이동: {nextPath}</span>}
      />

      <section className="mx-auto grid max-w-[1180px] gap-4 xl:grid-cols-[minmax(0,1.12fr)_360px]">
        <div className="card space-y-5">
          {mode !== "recovery" ? (
            <div className="ui-segmented-control">
              <button
                onClick={() => setModeInUrl("signin")}
                className={cn(
                  "ui-segmented-option",
                  mode === "signin" && "ui-segmented-option-active",
                )}
              >
                로그인
              </button>
              <button
                onClick={() => setModeInUrl("signup")}
                className={cn(
                  "ui-segmented-option",
                  mode === "signup" && "ui-segmented-option-active",
                )}
              >
                회원가입
              </button>
            </div>
          ) : (
            <div className="ui-panel-muted">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="text-sm font-semibold text-text">비밀번호 재설정 모드</div>
                  <p className="mt-1 text-xs leading-6 text-text-secondary">
                    복구 링크의 세션이 살아 있으면 여기서 새 비밀번호를 설정할 수 있습니다.
                  </p>
                </div>
                <button onClick={() => setModeInUrl("signin")} className="ui-button-secondary w-full shrink-0 sm:w-auto">
                  로그인으로 돌아가기
                </button>
              </div>
            </div>
          )}

          {mode === "signin" ? (
            <div className="space-y-4">
              <FormField label="이메일">
                <input
                  value={signinEmail}
                  onChange={(event) => setSigninEmail(event.target.value)}
                  type="email"
                  autoComplete="email"
                  className="ui-input"
                  placeholder="you@example.com"
                />
              </FormField>
              <FormField label="비밀번호">
                <input
                  value={signinPassword}
                  onChange={(event) => setSigninPassword(event.target.value)}
                  type="password"
                  autoComplete="current-password"
                  className="ui-input"
                  placeholder="비밀번호 입력"
                />
              </FormField>
              <div className="ui-panel-muted">
                <div className="ui-field-label">로그인 지원</div>
                <div className="ui-inline-actions mt-3">
                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={supportAction !== null || verificationCooldown.active}
                    className="ui-button-secondary"
                  >
                    {supportAction === "verification"
                      ? "전송 중..."
                      : verificationCooldown.active
                        ? `${verificationCooldown.seconds}초 후 다시`
                        : "인증 메일 다시 보내기"}
                  </button>
                  <button
                    type="button"
                    onClick={handlePasswordResetRequest}
                    disabled={supportAction !== null || resetCooldown.active}
                    className="ui-button-secondary"
                  >
                    {supportAction === "reset"
                      ? "전송 중..."
                      : resetCooldown.active
                        ? `${resetCooldown.seconds}초 후 다시`
                        : "비밀번호 재설정 메일"}
                  </button>
                </div>
                <p className="ui-helper-text mt-3">
                  로그인에 문제가 있으면 이메일을 먼저 입력한 뒤 인증 메일 재전송 또는 비밀번호 재설정 메일을 요청해 주세요. 같은 메일 액션은 60초 동안 잠시 쉬어 갑니다.
                </p>
              </div>
            </div>
          ) : null}

          {mode === "signup" ? (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  label="아이디"
                  helper="영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 사용할 수 있습니다. 입력 중 자동으로 소문자로 정리됩니다."
                >
                  <div className="flex flex-col gap-2 sm:flex-row">
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
                      className="ui-input min-w-0 flex-1"
                      placeholder="alpha_user"
                    />
                    <button
                      type="button"
                      onClick={handleUsernameCheck}
                      disabled={usernameState.checking || usernameCooldown.active}
                      className="ui-button-secondary shrink-0 sm:w-auto"
                    >
                      {usernameState.checking
                        ? "확인 중..."
                        : usernameCooldown.active
                          ? `${usernameCooldown.seconds}초 후 다시`
                          : "중복 확인"}
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
                    className="ui-input"
                    placeholder="you@example.com"
                  />
                </FormField>
                <FormField label="이름">
                  <input
                    value={signup.fullName}
                    onChange={(event) => updateSignupField("fullName", normalizeFullName(event.target.value).slice(0, 40))}
                    autoComplete="name"
                    maxLength={40}
                    className="ui-input"
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
                    className="ui-input"
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
                    className="ui-input"
                  />
                </FormField>
                <div className="ui-panel-muted">
                  <div className="ui-field-label">가입 체크</div>
                  <ul className="mt-3 space-y-2 text-[0.95rem] text-text-secondary">
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
                    className="ui-input"
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
                    className="ui-input"
                    placeholder="비밀번호 다시 입력"
                  />
                </FormField>
              </div>

              <PasswordStrengthChecklist result={passwordStrength} />
              {signupCooldown.active ? (
                <div className="ui-panel-warning text-[0.95rem] text-text-secondary">
                  회원가입 검증 요청이 잠시 많았습니다. {signupCooldown.seconds}초 후 다시 시도해 주세요.
                </div>
              ) : null}
            </div>
          ) : null}

          {mode === "recovery" ? (
            <div className="space-y-5">
              {session ? (
                <>
                  <div className="ui-panel-muted text-[0.95rem] text-text-secondary">
                    현재 복구 세션으로 연결된 계정은 <span className="font-medium text-text">{session.user.email ?? "이메일 정보 없음"}</span> 입니다.
                    새 비밀번호를 저장하면 다음 접속부터 새 비밀번호가 적용됩니다.
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField label="새 비밀번호">
                      <input
                        value={recoveryPassword}
                        onChange={(event) => setRecoveryPassword(event.target.value)}
                        type="password"
                        autoComplete="new-password"
                        maxLength={128}
                        className="ui-input"
                        placeholder="새 비밀번호 입력"
                      />
                    </FormField>
                    <FormField label="새 비밀번호 재확인">
                      <input
                        value={recoveryConfirm}
                        onChange={(event) => setRecoveryConfirm(event.target.value)}
                        type="password"
                        autoComplete="new-password"
                        maxLength={128}
                        className="ui-input"
                        placeholder="새 비밀번호 다시 입력"
                      />
                    </FormField>
                  </div>
                  <PasswordStrengthChecklist result={recoveryStrength} />
                </>
              ) : (
                <div className="ui-panel-warning text-[0.95rem] leading-6 text-text-secondary">
                  복구 세션이 아직 확인되지 않았습니다. 메일의 링크가 만료되었을 수 있으니 로그인 화면으로 돌아가 재설정 메일을 다시 요청해 주세요.
                </div>
              )}
            </div>
          ) : null}

          <button
            onClick={handleAuthSubmit}
            disabled={
              submitting ||
              loading ||
              usernameCooldown.active ||
              signupCooldown.active ||
              (mode === "signup" && !signUpReady) ||
              (mode === "recovery" && !recoveryReady)
            }
            className="ui-button-primary w-full"
          >
            {submitting
              ? "처리 중..."
              : mode === "signup" && signupCooldown.active
                ? `${signupCooldown.seconds}초 후 다시 시도`
              : mode === "signup"
                ? "회원가입하고 계속하기"
                : mode === "recovery"
                  ? "새 비밀번호 저장"
                  : "로그인하고 계속하기"}
          </button>

          {!configured ? (
            <div className="ui-panel-warning !px-4 !py-3 text-[0.95rem]">
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
