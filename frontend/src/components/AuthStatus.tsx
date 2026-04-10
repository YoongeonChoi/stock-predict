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
  if (fullName && username) return `${fullName} @${username}`;
  if (fullName) return fullName;
  if (username) return `@${username}`;
  if (email) return email.length > 26 ? `${email.slice(0, 23)}...` : email;
  return "로그인됨";
}

function buildCompactIdentityLabel({
  username,
  fullName,
  email,
}: {
  username?: string | null;
  fullName?: string | null;
  email?: string | null;
}) {
  if (username) return `@${username}`;
  if (fullName) return fullName;
  if (email) return email.length > 18 ? `${email.slice(0, 15)}...` : email;
  return "로그인됨";
}

export default function AuthStatus() {
  const router = useRouter();
  const { toast } = useToast();
  const { configured, loading, user, profile, signOut } = useAuth();

  if (!configured) {
    return (
      <div className="hidden text-[0.8rem] leading-6 text-warning md:block">
        인증 설정을 확인해 주세요.
      </div>
    );
  }

  if (loading) {
    return <div className="h-11 w-full animate-pulse rounded-[10px] bg-border/30 sm:w-48" />;
  }

  if (!user) {
    return (
      <div className="flex w-full shrink-0 flex-col gap-2 min-[420px]:flex-row min-[420px]:items-center min-[420px]:justify-end">
        <Link href="/auth" className="ui-button-secondary w-full px-4 min-[420px]:w-auto sm:px-5">
          로그인
        </Link>
        <Link href="/auth?mode=signup" className="ui-button-primary w-full px-4 min-[420px]:w-auto sm:px-5">
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
    <div className="flex w-full shrink-0 flex-col gap-2 min-[420px]:flex-row min-[420px]:items-center min-[420px]:justify-end min-[420px]:gap-2.5">
      <Link
        href="/settings"
        className="min-w-0 max-w-full rounded-[12px] border border-border/12 bg-surface px-3 py-2.5 text-left transition-colors hover:border-border/20 hover:bg-surface-muted min-[420px]:max-w-[248px] min-[420px]:text-right"
      >
        <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-secondary">Account</div>
        <div className="mt-1 truncate text-[0.9rem] font-semibold text-text sm:hidden">
          {buildCompactIdentityLabel({
            username: profile?.username,
            fullName: profile?.full_name,
            email: user.email,
          })}
        </div>
        <div className="mt-1 hidden text-[0.9rem] font-semibold text-text sm:block">
          {buildIdentityLabel({
            username: profile?.username,
            fullName: profile?.full_name,
            email: user.email,
          })}
        </div>
      </Link>
      <button onClick={handleSignOut} className="ui-button-secondary w-full px-4 min-[420px]:w-auto min-[420px]:shrink-0 sm:px-5">
        로그아웃
      </button>
    </div>
  );
}
