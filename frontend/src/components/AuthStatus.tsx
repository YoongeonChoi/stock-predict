"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useToast } from "@/components/Toast";
import { useAuth } from "@/components/AuthProvider";

function buildIdentityLabel({
  username,
  fullName,
  email,
}: {
  username?: string | null;
  fullName?: string | null;
  email?: string | null;
}) {
  if (fullName && username) {
    return `${fullName} · @${username}`;
  }
  if (fullName) {
    return fullName;
  }
  if (username) {
    return `@${username}`;
  }
  if (email) {
    return email.length > 26 ? `${email.slice(0, 23)}...` : email;
  }
  return "로그인됨";
}

export default function AuthStatus() {
  const router = useRouter();
  const { toast } = useToast();
  const { configured, loading, user, profile, signOut } = useAuth();

  if (!configured) {
    return (
      <div className="ui-panel-warning hidden px-3 py-2 text-xs text-amber-600 md:block">
        인증 설정을 확인해 주세요
      </div>
    );
  }

  if (loading) {
    return <div className="h-11 w-full animate-pulse rounded-[20px] bg-border/60 sm:w-48" />;
  }

  if (!user) {
    return (
      <div className="flex w-full shrink-0 flex-wrap items-center justify-end gap-2">
        <Link href="/auth" className="ui-button-secondary">
          로그인
        </Link>
        <Link href="/auth?mode=signup" className="ui-button-primary">
          회원가입
        </Link>
      </div>
    );
  }

  const handleSignOut = async () => {
    try {
      await signOut();
      toast("로그아웃했습니다.", "info");
      router.push("/");
      router.refresh();
    } catch {
      toast("로그아웃 중 문제가 발생했습니다.", "error");
    }
  };

  return (
    <div className="flex w-full shrink-0 flex-wrap items-center justify-end gap-2">
      <div className="min-w-0 max-w-full rounded-full border border-border/70 bg-surface/74 px-3.5 py-2.5 text-[0.88rem] text-text-secondary">
        {buildIdentityLabel({
          username: profile?.username,
          fullName: profile?.full_name,
          email: user.email,
        })}
      </div>
      <button onClick={handleSignOut} className="ui-button-secondary">
        로그아웃
      </button>
    </div>
  );
}
