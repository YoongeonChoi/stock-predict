"use client";

import { useEffect, useMemo, useState } from "react";

import { useCooldownTimer } from "@/hooks/useCooldownTimer";
import {
  describeAuthErrorMessage,
  isValidBirthDate,
  isValidFullName,
  isValidPhoneNumber,
  isValidUsername,
  normalizeFullName,
  normalizePhoneNumber,
  normalizeUsername,
} from "@/lib/account";
import { api, getApiRetryAfterSeconds, isApiErrorCode, type AccountProfile } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

export interface ProfileDraft {
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

interface UseAccountProfileSectionOptions {
  profile: AccountProfile | null;
  refreshProfile: () => Promise<void>;
  toast: (message: string, tone?: "info" | "success" | "error") => void;
}

export function useAccountProfileSection({
  profile,
  refreshProfile,
  toast,
}: UseAccountProfileSectionOptions) {
  const [draft, setDraft] = useState<ProfileDraft>(buildDraft(profile));
  const [usernameState, setUsernameState] = useState<UsernameState>(buildUsernameState(profile));
  const [saving, setSaving] = useState(false);
  const usernameCooldown = useCooldownTimer();

  useEffect(() => {
    setDraft(buildDraft(profile));
    setUsernameState(buildUsernameState(profile));
  }, [profile?.birth_date, profile?.full_name, profile?.phone_number, profile?.user_id, profile?.username]);

  const normalizedCurrentUsername = normalizeUsername(profile?.username ?? "");
  const normalizedDraftUsername = normalizeUsername(draft.username);

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

  const resetProfileDraft = () => {
    setDraft(buildDraft(profile));
    setUsernameState(buildUsernameState(profile));
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

  return {
    draft,
    usernameState,
    saving,
    usernameCooldown,
    usernameReady,
    isDirty,
    formValid,
    updateDraft,
    resetProfileDraft,
    handleUsernameCheck,
    handleSave,
  };
}
