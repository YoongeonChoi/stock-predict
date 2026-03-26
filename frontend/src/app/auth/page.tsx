"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import PageHeader from "@/components/PageHeader";
import { useAuth } from "@/components/AuthProvider";
import { useToast } from "@/components/Toast";
import { getSupabaseBrowserClient } from "@/lib/supabase-browser";

type AuthMode = "signin" | "signup";

function AuthPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const { configured, loading, session } = useAuth();
  const [mode, setMode] = useState<AuthMode>(searchParams.get("mode") === "signup" ? "signup" : "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const nextPath = searchParams.get("next") || "/portfolio";

  useEffect(() => {
    if (!loading && session) {
      router.replace(nextPath);
    }
  }, [loading, nextPath, router, session]);

  const handleSubmit = async () => {
    const client = getSupabaseBrowserClient();
    if (!configured || !client) {
      toast("Supabase 설정이 비어 있어 로그인 화면을 열 수 없습니다.", "error");
      return;
    }
    if (!email.trim() || !password) {
      toast("이메일과 비밀번호를 모두 입력해 주세요.", "error");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "signup") {
        const redirectTo = `${window.location.origin}${nextPath}`;
        const { data, error } = await client.auth.signUp({
          email: email.trim(),
          password,
          options: { emailRedirectTo: redirectTo },
        });
        if (error) {
          throw error;
        }
        if (data.session) {
          toast("회원가입과 로그인이 완료되었습니다.", "success");
          router.replace(nextPath);
        } else {
          toast("가입 확인 메일을 보냈습니다. 메일 인증 후 다시 로그인해 주세요.", "info");
          setMode("signin");
        }
      } else {
        const { error } = await client.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (error) {
          throw error;
        }
        toast("로그인되었습니다.", "success");
        router.replace(nextPath);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "인증 처리 중 문제가 발생했습니다.";
      toast(message, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page-shell space-y-5">
      <PageHeader
        eyebrow="계정"
        title="로그인 및 회원가입"
        description="워치리스트와 포트폴리오를 계정별로 분리해 저장하려면 로그인부터 연결해 주세요."
        meta={<span className="info-chip">다음 이동: {nextPath}</span>}
      />

      <section className="mx-auto grid max-w-4xl gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
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

          <div className="grid gap-4">
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">이메일</label>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                autoComplete="email"
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.16em] text-text-secondary">비밀번호</label>
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                className="w-full rounded-2xl border border-border bg-surface/60 px-4 py-3 text-sm"
                placeholder="8자 이상 권장"
              />
            </div>
          </div>

          <button onClick={handleSubmit} disabled={submitting || loading} className="action-chip-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-60">
            {submitting ? "처리 중..." : mode === "signup" ? "회원가입하고 계속하기" : "로그인하고 계속하기"}
          </button>

          {!configured ? (
            <div className="rounded-2xl border border-negative/20 bg-negative/5 px-4 py-3 text-sm text-negative">
              Supabase 브라우저 설정이 비어 있습니다. `NEXT_PUBLIC_SUPABASE_URL`과 `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`를 확인해 주세요.
            </div>
          ) : null}
        </div>

        <aside className="card !p-5 space-y-3">
          <div className="text-sm font-semibold text-text">인증 후 바로 열리는 기능</div>
          <ul className="space-y-2 text-sm leading-7 text-text-secondary">
            <li>관심종목을 사용자별로 완전히 분리해 저장합니다.</li>
            <li>포트폴리오, 자산 기준, 추천 결과를 내 계정 기준으로 계산합니다.</li>
            <li>같은 브라우저에서 다시 접속해도 세션이 유지됩니다.</li>
          </ul>
        </aside>
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
