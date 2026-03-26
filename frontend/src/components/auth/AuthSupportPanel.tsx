"use client";

import { ShieldCheck, UserRoundCheck, WalletCards } from "lucide-react";

const ITEMS = [
  {
    icon: ShieldCheck,
    title: "보안 우선 회원가입",
    description: "비밀번호 강도, 아이디 중복, 필수 개인정보 입력을 한 번에 확인한 뒤 가입을 진행합니다.",
  },
  {
    icon: UserRoundCheck,
    title: "계정별 데이터 분리",
    description: "관심종목과 포트폴리오, 자산 기준은 계정마다 완전히 분리되어 저장됩니다.",
  },
  {
    icon: WalletCards,
    title: "접속 후 바로 이어서 사용",
    description: "한 번 로그인하면 같은 브라우저에서 세션을 유지하고, 다시 들어와도 작업 흐름이 이어집니다.",
  },
];

export default function AuthSupportPanel() {
  return (
    <aside className="card !p-5 space-y-4">
      <div>
        <div className="text-sm font-semibold text-text">계정 연결 후 바로 가능한 일</div>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          로그인 이후에는 관심종목, 포트폴리오, 추천 결과가 모두 내 계정 기준으로 이어집니다.
        </p>
      </div>
      <div className="space-y-3">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.title} className="rounded-[20px] border border-border/70 bg-surface/55 p-4">
              <div className="flex items-start gap-3">
                <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
                  <Icon size={18} />
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-text">{item.title}</div>
                  <p className="mt-1 text-xs leading-6 text-text-secondary">{item.description}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
