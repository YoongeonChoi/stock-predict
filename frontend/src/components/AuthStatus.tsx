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
      <div className="hidden rounded-2xl border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-600 md:block">
        인증 설정을 확인해 주세요
      </div>
    );
  }

  if (loading) {
    return <div className="hidden h-10 w-40 animate-pulse rounded-2xl bg-border/60 md:block" />;
  }

  if (!user) {
    return (
      <div className="flex shrink-0 items-center gap-2">
        <Link href="/auth" className="action-chip-secondary">
          로그인
        </Link>
        <Link href="/auth?mode=signup" className="hidden rounded-2xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-soft transition-opacity hover:opacity-90 md:inline-flex">
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
    <div className="flex shrink-0 items-center gap-2">
      <div className="hidden rounded-2xl border border-border/70 bg-surface/70 px-3 py-2 text-sm text-text-secondary md:block">
        {buildIdentityLabel({
          username: profile?.username,
          fullName: profile?.full_name,
          email: user.email,
        })}
      </div>
      <button onClick={handleSignOut} className="action-chip-secondary">
        로그아웃
      </button>
    </div>
  );
}
