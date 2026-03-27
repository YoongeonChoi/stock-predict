"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { KeyRound, MailCheck, ShieldAlert, Trash2, UserRound } from "lucide-react";

import PasswordStrengthChecklist from "@/components/auth/PasswordStrengthChecklist";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { useCooldownTimer } from "@/hooks/useCooldownTimer";
import {
  formatPhoneNumber,
  describeAuthErrorMessage,
  getPasswordStrength,
  isValidEmail,
  isValidBirthDate,
  isValidFullName,
  isValidPhoneNumber,
  isValidUsername,
  normalizeEmail,
  normalizeFullName,
  normalizePhoneNumber,
  normalizeUsername,
} from "@/lib/account";
import { api, getApiRetryAfterSeconds, isApiErrorCode, type AccountProfile } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

interface ProfileDraft {
  username: string;
  fullName: string;
  phoneNumber: string;
  birthDate: string;
}

interface UsernameState {
  checkedValue: string;
  valid: boolean;
  available: boolean;
  checking: boolean;
  message: string;
}

interface PasswordDraft {
  nextPassword: string;
  confirmPassword: string;
}

interface EmailDraft {
  nextEmail: string;
  confirmEmail: string;
}

function buildDraft(profile: AccountProfile | null): ProfileDraft {
  return {
    username: profile?.username ?? "",
    fullName: profile?.full_name ?? "",
    phoneNumber: profile?.phone_number ?? "",
    birthDate: profile?.birth_date ?? "",
  };
}

function buildUsernameState(profile: AccountProfile | null): UsernameState {
  const current = normalizeUsername(profile?.username ?? "");
  return {
    checkedValue: current,
    valid: Boolean(current),
    available: Boolean(current),
    checking: false,
    message: current ? "현재 아이디가 유지됩니다." : "아이디를 입력하고 중복 확인을 진행해 주세요.",
  };
}

function Field({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">{label}</label>
      {children}
      {helper ? <div className="mt-2 text-xs leading-5 text-text-secondary">{helper}</div> : null}
    </div>
  );
}

export default function AccountSettingsPanel() {
  const { configured, loading, session, user, profile, profileLoading, refreshProfile, signOut, signOutEverywhere } = useAuth();
  const { toast } = useToast();
  const [draft, setDraft] = useState<ProfileDraft>(buildDraft(profile));
  const [usernameState, setUsernameState] = useState<UsernameState>(buildUsernameState(profile));
  const [saving, setSaving] = useState(false);
  const [sendingVerification, setSendingVerification] = useState(false);
  const [sendingReset, setSendingReset] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signingOutEverywhere, setSigningOutEverywhere] = useState(false);
  const [passwordDraft, setPasswordDraft] = useState<PasswordDraft>({ nextPassword: "", confirmPassword: "" });
  const [emailDraft, setEmailDraft] = useState<EmailDraft>({ nextEmail: "", confirmEmail: "" });
  const [updatingEmail, setUpdatingEmail] = useState(false);
  const [updatingPassword, setUpdatingPassword] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deletingAccount, setDeletingAccount] = useState(false);
  const usernameCooldown = useCooldownTimer();
  const emailChangeCooldown = useCooldownTimer();
  const verificationCooldown = useCooldownTimer();
  const resetCooldown = useCooldownTimer();

  useEffect(() => {
    setDraft(buildDraft(profile));
    setUsernameState(buildUsernameState(profile));
  }, [profile?.birth_date, profile?.full_name, profile?.phone_number, profile?.user_id, profile?.username]);

  const normalizedCurrentUsername = normalizeUsername(profile?.username ?? "");
  const normalizedDraftUsername = normalizeUsername(draft.username);
  const passwordStrength = useMemo(
    () => getPasswordStrength(passwordDraft.nextPassword, passwordDraft.confirmPassword),
    [passwordDraft.confirmPassword, passwordDraft.nextPassword],
  );
  const passwordReady = Boolean(
    passwordStrength.checks.minLength &&
    passwordStrength.checks.uppercase &&
    passwordStrength.checks.lowercase &&
    passwordStrength.checks.number &&
    passwordStrength.checks.symbol &&
    passwordStrength.checks.match,
  );
  const deleteTargetLabel = profile?.username ? "현재 아이디" : "현재 이메일";
  const deleteTargetValue = profile?.username ? normalizedCurrentUsername : (profile?.email ?? "").trim().toLowerCase();
  const deleteReady = Boolean(deleteTargetValue) && (
    profile?.username
      ? normalizeUsername(deleteConfirmation) === deleteTargetValue
      : deleteConfirmation.trim().toLowerCase() === deleteTargetValue
  );
  const lastSignInLabel = user?.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleString("ko-KR") : "확인 불가";
  const sessionExpiryLabel =
    typeof session?.expires_at === "number"
      ? new Date(session.expires_at * 1000).toLocaleString("ko-KR")
      : "확인 불가";
  const pendingEmail = normalizeEmail(profile?.pending_email ?? "");
  const currentEmail = normalizeEmail(profile?.email ?? "");
  const normalizedNextEmail = normalizeEmail(emailDraft.nextEmail);
  const emailChangeSentLabel = profile?.email_change_sent_at
    ? new Date(profile.email_change_sent_at).toLocaleString("ko-KR")
    : "확인 불가";
  const emailMatches = Boolean(emailDraft.nextEmail) && normalizedNextEmail === normalizeEmail(emailDraft.confirmEmail);
  const emailReady = Boolean(
    isValidEmail(normalizedNextEmail) &&
    emailMatches &&
    normalizedNextEmail !== currentEmail &&
    normalizedNextEmail !== pendingEmail,
  );
  const usernameReady =
    Boolean(normalizedDraftUsername) &&
    (
      normalizedDraftUsername === normalizedCurrentUsername ||
      (
        usernameState.checkedValue === normalizedDraftUsername &&
        usernameState.valid &&
        usernameState.available
      )
    );

  const isDirty = useMemo(() => {
    return (
      normalizeUsername(draft.username) !== normalizeUsername(profile?.username ?? "") ||
      normalizeFullName(draft.fullName) !== normalizeFullName(profile?.full_name ?? "") ||
      normalizePhoneNumber(draft.phoneNumber) !== normalizePhoneNumber(profile?.phone_number ?? "") ||
      draft.birthDate !== (profile?.birth_date ?? "")
    );
  }, [draft, profile]);

  const formValid =
    isValidUsername(draft.username) &&
    isValidFullName(draft.fullName) &&
    isValidPhoneNumber(draft.phoneNumber) &&
    isValidBirthDate(draft.birthDate) &&
    usernameReady;

  const updateDraft = <K extends keyof ProfileDraft>(key: K, value: ProfileDraft[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
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

    if (!isValidUsername(draft.username)) {
      setUsernameState({
        checkedValue: normalizedDraftUsername,
        valid: false,
        available: false,
        checking: false,
        message: "아이디는 영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 4~20자까지 사용할 수 있습니다.",
      });
      return;
    }

    setUsernameState((prev) => ({ ...prev, checking: true }));
    try {
      const result = await api.checkUsernameAvailability(draft.username);
      const available =
        result.available || result.normalized_username === normalizedCurrentUsername;
      setUsernameState({
        checkedValue: result.normalized_username,
        valid: result.valid,
        available,
        checking: false,
        message: available
          ? (result.normalized_username === normalizedCurrentUsername ? "현재 아이디를 그대로 사용할 수 있습니다." : "사용 가능한 아이디입니다.")
          : result.message,
      });
    } catch (error) {
      if (isApiErrorCode(error, "SP-6016")) {
        const retryAfter = getApiRetryAfterSeconds(error) ?? 30;
        usernameCooldown.start(retryAfter);
        setUsernameState({
          checkedValue: normalizedDraftUsername,
          valid: false,
          available: false,
          checking: false,
          message: error.detail || `중복 확인 요청이 많아 ${retryAfter}초 후 다시 시도해 주세요.`,
        });
        return;
      }
      setUsernameState({
        checkedValue: normalizedDraftUsername,
        valid: false,
        available: false,
        checking: false,
        message: describeAuthErrorMessage(error, "중복 확인 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."),
      });
    }
  };

  const handleSave = async () => {
    if (!formValid) {
      toast("필수 입력과 아이디 중복 확인을 먼저 완료해 주세요.", "error");
      return;
    }

    setSaving(true);
    try {
      const nextProfile = await api.updateMyAccountProfile({
        username: normalizedDraftUsername,
        full_name: normalizeFullName(draft.fullName),
        phone_number: normalizePhoneNumber(draft.phoneNumber),
        birth_date: draft.birthDate,
      });
      const client = getSupabaseBrowserClient();
      if (client) {
        await client.auth.refreshSession();
      }
      await refreshProfile();
      setDraft(buildDraft(nextProfile));
      setUsernameState(buildUsernameState(nextProfile));
      toast("계정 정보가 저장되었습니다.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "계정 정보 저장 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleResendVerification = async () => {
    const targetEmail = profile?.pending_email ?? profile?.email;
    const resendType = profile?.pending_email ? "email_change" : "signup";
    if (!targetEmail) {
      toast("인증 메일을 보낼 이메일이 없습니다.", "error");
      return;
    }
    if (verificationCooldown.active) {
      toast(`인증 메일은 ${verificationCooldown.seconds}초 후 다시 보낼 수 있습니다.`, "error");
      return;
    }
    const client = getSupabaseBrowserClient();
    if (!client) {
      toast("Supabase 설정이 비어 있어 인증 메일을 보낼 수 없습니다.", "error");
      return;
    }

    setSendingVerification(true);
    try {
      const { error } = await client.auth.resend({
        type: resendType,
        email: targetEmail,
        options: {
          emailRedirectTo: `${window.location.origin}/settings`,
        },
      });
      if (error) {
        throw error;
      }
      verificationCooldown.start(60);
      toast("인증 메일을 다시 보냈습니다. 받은 편지함을 확인해 주세요.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "인증 메일 재전송에 실패했습니다.";
      toast(message, "error");
    } finally {
      setSendingVerification(false);
    }
  };

  const handleSendPasswordReset = async () => {
    if (!profile?.email) {
      toast("비밀번호 재설정 메일을 보낼 이메일이 없습니다.", "error");
      return;
    }
    if (resetCooldown.active) {
      toast(`재설정 메일은 ${resetCooldown.seconds}초 후 다시 요청할 수 있습니다.`, "error");
      return;
    }
    const client = getSupabaseBrowserClient();
    if (!client) {
      toast("Supabase 설정이 비어 있어 재설정 메일을 보낼 수 없습니다.", "error");
      return;
    }

    setSendingReset(true);
    try {
      const { error } = await client.auth.resetPasswordForEmail(profile.email, {
        redirectTo: `${window.location.origin}/auth?mode=recovery&next=/settings`,
      });
      if (error) {
        throw error;
      }
      resetCooldown.start(60);
      toast("비밀번호 재설정 메일을 보냈습니다. 메일의 링크에서 새 비밀번호를 설정해 주세요.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "비밀번호 재설정 메일 전송에 실패했습니다.";
      toast(message, "error");
    } finally {
      setSendingReset(false);
    }
  };

  const handleEmailChange = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      toast("Supabase 설정이 비어 있어 이메일을 변경할 수 없습니다.", "error");
      return;
    }
    if (emailChangeCooldown.active) {
      toast(`이메일 변경 요청은 ${emailChangeCooldown.seconds}초 후 다시 보낼 수 있습니다.`, "error");
      return;
    }
    if (!isValidEmail(normalizedNextEmail)) {
      toast("새 이메일 형식을 올바르게 입력해 주세요.", "error");
      return;
    }
    if (!emailMatches) {
      toast("새 이메일 재확인이 일치하지 않습니다.", "error");
      return;
    }
    if (normalizedNextEmail === currentEmail) {
      toast("현재 사용 중인 이메일과 다른 주소를 입력해 주세요.", "error");
      return;
    }
    if (normalizedNextEmail === pendingEmail) {
      toast("이미 변경 대기 중인 이메일입니다. 받은 편지함의 인증 메일을 먼저 확인해 주세요.", "error");
      return;
    }

    setUpdatingEmail(true);
    try {
      const { error } = await client.auth.updateUser(
        { email: normalizedNextEmail },
        { emailRedirectTo: `${window.location.origin}/settings` },
      );
      if (error) {
        throw error;
      }
      emailChangeCooldown.start(60);
      setEmailDraft({ nextEmail: "", confirmEmail: "" });
      await refreshProfile();
      toast("이메일 변경 요청을 보냈습니다. 새 주소의 인증 메일을 확인해 주세요.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "이메일 변경 요청 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setUpdatingEmail(false);
    }
  };

  const handleUpdatePassword = async () => {
    const client = getSupabaseBrowserClient();
    if (!client) {
      toast("Supabase 설정이 비어 있어 비밀번호를 변경할 수 없습니다.", "error");
      return;
    }
    if (!passwordReady) {
      toast("새 비밀번호 보안 조건과 재확인을 모두 만족해 주세요.", "error");
      return;
    }

    setUpdatingPassword(true);
    try {
      const { error } = await client.auth.updateUser({ password: passwordDraft.nextPassword });
      if (error) {
        throw error;
      }
      setPasswordDraft({ nextPassword: "", confirmPassword: "" });
      toast("새 비밀번호가 저장되었습니다.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "비밀번호 변경 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setUpdatingPassword(false);
    }
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut();
      toast("로그아웃되었습니다.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "로그아웃 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setSigningOut(false);
    }
  };

  const handleGlobalSignOut = async () => {
    if (!window.confirm("이 기기를 포함해 현재 계정으로 열려 있는 다른 세션도 모두 종료합니다. 계속 진행할까요?")) {
      return;
    }

    setSigningOutEverywhere(true);
    try {
      await signOutEverywhere();
      toast("모든 기기에서 로그아웃되었습니다. 다시 로그인해 주세요.", "success");
      window.location.assign("/auth");
    } catch (error) {
      const message = error instanceof Error ? error.message : "전체 로그아웃 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setSigningOutEverywhere(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!deleteReady) {
      toast(`${deleteTargetLabel}를 정확히 입력한 뒤 회원 탈퇴를 진행해 주세요.`, "error");
      return;
    }
    if (!window.confirm("계정을 삭제하면 관심종목, 포트폴리오, 계정 설정이 함께 제거됩니다. 계속 진행할까요?")) {
      return;
    }

    setDeletingAccount(true);
    try {
      const result = await api.deleteMyAccount({ confirmation_text: deleteConfirmation });
      const client = getSupabaseBrowserClient();
      if (client) {
        try {
          await client.auth.signOut({ scope: "local" });
        } catch {
          // Deletion may invalidate the remote session before sign-out finishes.
        }
      }
      toast(result.message, "success");
      window.location.assign("/auth");
    } catch (error) {
      const message = error instanceof Error ? error.message : "회원 탈퇴 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setDeletingAccount(false);
    }
  };

  if (!configured) {
    return (
      <section className="card !p-5 space-y-3">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <ShieldAlert size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold">계정 관리</h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              Supabase 브라우저 설정이 비어 있어 계정 정보를 불러올 수 없습니다.
            </p>
          </div>
        </div>
      </section>
    );
  }

  if (loading || profileLoading) {
    return <div className="card h-[320px] animate-pulse" />;
  }

  if (!session || !user || !profile) {
    return (
      <section className="card !p-5 space-y-4">
        <div className="flex items-start gap-3">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <UserRound size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold">계정 관리</h2>
            <p className="mt-1 text-sm leading-6 text-text-secondary">
              계정별 포트폴리오와 관심종목을 관리하려면 로그인부터 연결해 주세요.
            </p>
          </div>
        </div>
        <div className="rounded-[22px] border border-border/70 bg-surface/55 p-4 text-sm text-text-secondary">
          로그인 후에는 이름, 전화번호, 생년월일, 아이디를 수정하고 인증 메일 재전송, 비밀번호 변경, 세션 종료 같은 보안 작업도 바로 처리할 수 있습니다.
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/auth?next=/settings" className="action-chip-primary">
            로그인하러 가기
          </Link>
          <Link href="/auth?mode=signup&next=/settings" className="action-chip-secondary">
            회원가입하기
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="card !p-5 space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">계정 관리</h2>
            <span className={`info-chip ${profile.email_verified ? "!bg-positive/10 !text-positive" : "!bg-warning/10 !text-warning"}`}>
              {profile.email_verified ? "이메일 인증 완료" : "이메일 인증 필요"}
            </span>
          </div>
          <p className="text-sm leading-6 text-text-secondary">
            프로필 정보와 보안 관련 작업을 한 곳에서 관리합니다. 아이디를 바꾸는 경우에는 다시 중복 확인을 거쳐야 하며, 요청이 많으면 잠시 후 재시도 안내가 표시됩니다.
          </p>
        </div>
        <div className="rounded-[22px] border border-border/70 bg-surface/55 px-4 py-3 text-sm">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">로그인 계정</div>
          <div className="mt-2 font-medium text-text">{profile.email ?? "이메일 없음"}</div>
          <div className="mt-1 text-xs text-text-secondary">
            {profile.email_confirmed_at
              ? `인증 완료 시각 ${new Date(profile.email_confirmed_at).toLocaleString("ko-KR")}`
              : "아직 이메일 인증이 완료되지 않았습니다."}
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.16fr)_340px]">
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="아이디"
              helper="영문 소문자로 시작하고 영문 소문자, 숫자, 밑줄만 4~20자까지 사용할 수 있습니다."
            >
              <div className="flex gap-2">
                <input
                  value={draft.username}
                  onChange={(event) =>
                    updateDraft(
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
                  disabled={usernameState.checking || usernameCooldown.active}
                  className="action-chip-secondary shrink-0"
                >
                  {usernameState.checking
                    ? "확인 중..."
                    : usernameCooldown.active
                      ? `${usernameCooldown.seconds}초 후 다시`
                      : "중복 확인"}
                </button>
              </div>
            </Field>

            <Field label="이메일" helper="이메일은 인증과 비밀번호 재설정에 사용됩니다.">
              <input
                value={profile.email ?? ""}
                readOnly
                className="w-full rounded-2xl border border-border bg-surface/40 px-4 py-3 text-sm text-text-secondary"
              />
            </Field>

            <Field label="이름">
              <input
                value={draft.fullName}
                onChange={(event) => updateDraft("fullName", normalizeFullName(event.target.value).slice(0, 40))}
                autoComplete="name"
                maxLength={40}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                placeholder="홍길동"
              />
            </Field>

            <Field label="전화번호" helper="하이픈 없이 입력해도 자동으로 정리됩니다.">
              <input
                value={draft.phoneNumber}
                onChange={(event) => updateDraft("phoneNumber", formatPhoneNumber(event.target.value))}
                inputMode="numeric"
                autoComplete="tel"
                maxLength={15}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                placeholder="010-1234-5678"
              />
            </Field>

            <Field label="생년월일">
              <input
                value={draft.birthDate}
                onChange={(event) => updateDraft("birthDate", event.target.value)}
                type="date"
                autoComplete="bday"
                max={new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
              />
            </Field>

            <div className="rounded-[22px] border border-border/70 bg-surface/50 px-4 py-4">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">현재 검증 상태</div>
              <ul className="mt-3 space-y-2 text-sm text-text-secondary">
                <li>{isValidFullName(draft.fullName) ? "이름 형식이 확인되었습니다." : "이름은 2자 이상으로 입력해 주세요."}</li>
                <li>{isValidPhoneNumber(draft.phoneNumber) ? "전화번호 형식이 확인되었습니다." : "전화번호를 올바르게 입력해 주세요."}</li>
                <li>{isValidBirthDate(draft.birthDate) ? "생년월일 형식이 확인되었습니다." : "생년월일을 선택해 주세요."}</li>
                <li className={usernameReady ? "text-positive" : ""}>{usernameState.message}</li>
              </ul>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !isDirty || !formValid}
              className="action-chip-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "저장 중..." : "프로필 저장"}
            </button>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-[24px] border border-border/70 bg-surface/55 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                <MailCheck size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">이메일 인증 관리</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  인증이 완료되지 않았거나 메일을 다시 받아야 할 때 바로 재전송할 수 있습니다.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleResendVerification}
              disabled={
                sendingVerification ||
                verificationCooldown.active ||
                (!profile.email && !profile.pending_email) ||
                (profile.email_verified && !profile.pending_email)
              }
              className="action-chip-secondary mt-4 w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
            >
              {profile.pending_email
                ? (sendingVerification
                  ? "재전송 중..."
                  : verificationCooldown.active
                    ? `${verificationCooldown.seconds}초 후 다시`
                    : "변경 확인 메일 다시 보내기")
                : profile.email_verified
                  ? "이메일 인증 완료"
                  : sendingVerification
                    ? "재전송 중..."
                    : verificationCooldown.active
                      ? `${verificationCooldown.seconds}초 후 다시`
                      : "인증 메일 다시 보내기"}
            </button>
            <p className="mt-3 text-xs leading-6 text-text-secondary">
              같은 인증 메일 액션은 60초 동안 잠시 쉬어 갑니다.
            </p>
            {profile.pending_email ? (
              <div className="mt-4 rounded-[20px] border border-border/70 bg-surface/60 px-4 py-4 text-sm text-text-secondary">
                <div className="font-medium text-text">변경 대기 이메일</div>
                <div className="mt-1 break-all">{profile.pending_email}</div>
                <div className="mt-2 text-xs leading-6">보낸 시각: {emailChangeSentLabel}</div>
              </div>
            ) : null}
          </div>

          <div className="rounded-[24px] border border-border/70 bg-surface/55 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                <MailCheck size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">이메일 변경</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  로그인 메일 주소를 바꾸면 새 주소로 확인 메일이 발송됩니다. 메일 확인 전까지는 현재 주소가 유지됩니다.
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <Field label="현재 이메일">
                <input
                  value={profile.email ?? ""}
                  readOnly
                  className="w-full rounded-2xl border border-border bg-surface/40 px-4 py-3 text-sm text-text-secondary"
                />
              </Field>
              <Field
                label="새 이메일"
                helper={
                  pendingEmail
                    ? "이미 변경 대기 중인 주소와 다른 이메일만 새로 요청할 수 있습니다."
                    : "인증 메일은 새 이메일 주소로 발송되며 같은 요청은 60초 동안 잠시 쉬어 갑니다."
                }
              >
                <input
                  value={emailDraft.nextEmail}
                  onChange={(event) => setEmailDraft((prev) => ({ ...prev, nextEmail: event.target.value }))}
                  type="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="new@example.com"
                />
              </Field>
              <Field label="새 이메일 재확인">
                <input
                  value={emailDraft.confirmEmail}
                  onChange={(event) => setEmailDraft((prev) => ({ ...prev, confirmEmail: event.target.value }))}
                  type="email"
                  autoComplete="email"
                  autoCapitalize="none"
                  spellCheck={false}
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="new@example.com"
                />
              </Field>
              <div className="rounded-[20px] border border-border/70 bg-surface/60 px-4 py-4 text-sm text-text-secondary">
                <ul className="space-y-2">
                  <li>{isValidEmail(normalizedNextEmail) ? "새 이메일 형식이 확인되었습니다." : "새 이메일 형식을 확인해 주세요."}</li>
                  <li>{emailMatches ? "이메일 재확인이 일치합니다." : "새 이메일 재확인을 동일하게 입력해 주세요."}</li>
                  <li>{normalizedNextEmail && normalizedNextEmail === currentEmail ? "현재 이메일과 같은 주소는 사용할 수 없습니다." : "현재 이메일과 다른 주소를 요청할 수 있습니다."}</li>
                  <li>{pendingEmail && normalizedNextEmail === pendingEmail ? "이미 변경 대기 중인 이메일입니다." : "변경 대기 중인 이메일과 충돌하지 않습니다."}</li>
                </ul>
              </div>
              <button
                type="button"
                onClick={handleEmailChange}
                disabled={updatingEmail || emailChangeCooldown.active || !emailReady}
                className="action-chip-secondary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
              >
                {updatingEmail
                  ? "변경 요청 중..."
                  : emailChangeCooldown.active
                    ? `${emailChangeCooldown.seconds}초 후 다시`
                    : "새 이메일로 변경 요청"}
              </button>
              <p className="text-xs leading-6 text-text-secondary">
                이메일 변경 요청도 같은 주소로 60초 동안 연속 발송되지 않도록 잠시 대기합니다.
              </p>
            </div>
          </div>

          <div className="rounded-[24px] border border-border/70 bg-surface/55 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                <ShieldAlert size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">세션 보안</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  마지막 로그인과 현재 세션 만료 시각을 확인하고, 필요하면 다른 기기 세션까지 한 번에 종료할 수 있습니다.
                </p>
              </div>
            </div>
            <dl className="mt-4 space-y-3 rounded-[20px] border border-border/70 bg-surface/60 px-4 py-4 text-sm">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-text-secondary">마지막 로그인</dt>
                <dd className="text-right font-medium text-text">{lastSignInLabel}</dd>
              </div>
              <div className="flex items-start justify-between gap-4">
                <dt className="text-text-secondary">현재 세션 만료</dt>
                <dd className="text-right font-medium text-text">{sessionExpiryLabel}</dd>
              </div>
            </dl>
            <div className="mt-4 flex flex-col gap-2">
              <button
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
                className="action-chip-secondary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
              >
                {signingOut ? "로그아웃 중..." : "이 기기에서 로그아웃"}
              </button>
              <button
                type="button"
                onClick={handleGlobalSignOut}
                disabled={signingOutEverywhere}
                className="inline-flex w-full items-center justify-center rounded-2xl border border-border bg-white/80 px-4 py-3 text-sm font-semibold text-text transition hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
              >
                {signingOutEverywhere ? "전체 로그아웃 중..." : "모든 기기에서 로그아웃"}
              </button>
            </div>
          </div>

          <div className="rounded-[24px] border border-border/70 bg-surface/55 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                <KeyRound size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">비밀번호 바로 변경</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  로그인된 상태라면 새 비밀번호를 바로 적용할 수 있습니다. 회원가입과 같은 강도 규칙을 만족해야 저장됩니다.
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <Field label="새 비밀번호">
                <input
                  value={passwordDraft.nextPassword}
                  onChange={(event) => setPasswordDraft((prev) => ({ ...prev, nextPassword: event.target.value }))}
                  type="password"
                  autoComplete="new-password"
                  maxLength={128}
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="새 비밀번호 입력"
                />
              </Field>
              <Field label="새 비밀번호 재확인">
                <input
                  value={passwordDraft.confirmPassword}
                  onChange={(event) => setPasswordDraft((prev) => ({ ...prev, confirmPassword: event.target.value }))}
                  type="password"
                  autoComplete="new-password"
                  maxLength={128}
                  className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                  placeholder="새 비밀번호 다시 입력"
                />
              </Field>
              <PasswordStrengthChecklist result={passwordStrength} />
              <button
                type="button"
                onClick={handleUpdatePassword}
                disabled={updatingPassword || !passwordReady}
                className="action-chip-secondary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
              >
                {updatingPassword ? "비밀번호 저장 중..." : "새 비밀번호 저장"}
              </button>
            </div>
          </div>

          <div className="rounded-[24px] border border-border/70 bg-surface/55 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                <MailCheck size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">비밀번호 재설정 메일</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  현재 세션이 불안정하거나 메일 링크 방식이 더 편할 때는 재설정 메일을 보내 새 비밀번호를 설정할 수 있습니다.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleSendPasswordReset}
              disabled={sendingReset || resetCooldown.active || !profile.email}
              className="action-chip-secondary mt-4 w-full justify-center disabled:cursor-not-allowed disabled:opacity-60"
            >
              {sendingReset
                ? "메일 전송 중..."
                : resetCooldown.active
                  ? `${resetCooldown.seconds}초 후 다시`
                  : "비밀번호 재설정 메일 보내기"}
            </button>
            <p className="mt-3 text-xs leading-6 text-text-secondary">
              재설정 메일도 같은 주소로 60초 동안 연속 발송되지 않도록 잠시 대기합니다.
            </p>
          </div>

          <div className="rounded-[24px] border border-warning/30 bg-warning/10 p-4">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-warning/20 text-warning">
                <Trash2 size={18} />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-text">회원 탈퇴</div>
                <p className="mt-1 text-xs leading-6 text-text-secondary">
                  계정을 삭제하면 관심종목, 보유 종목, 포트폴리오 프로필이 함께 정리되며 되돌릴 수 없습니다.
                </p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <Field
                label={deleteTargetLabel}
                helper={`탈퇴를 진행하려면 ${deleteTargetLabel} (${profile?.username ?? profile?.email ?? "-"})를 다시 입력해 주세요.`}
              >
                <input
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  autoCapitalize="none"
                  autoComplete="off"
                  spellCheck={false}
                  className="w-full rounded-2xl border border-warning/40 bg-surface/75 px-4 py-3 text-sm"
                  placeholder={profile?.username ?? profile?.email ?? ""}
                />
              </Field>
              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={deletingAccount || !deleteReady}
                className="inline-flex w-full items-center justify-center rounded-2xl border border-warning/40 bg-white/80 px-4 py-3 text-sm font-semibold text-warning transition hover:bg-warning/10 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deletingAccount ? "계정 삭제 중..." : "회원 탈퇴"}
              </button>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
