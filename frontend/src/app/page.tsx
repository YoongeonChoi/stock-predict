import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Crosshair,
  DatabaseZap,
  LineChart,
  ListFilter,
  PieChart,
  ShieldCheck,
} from "lucide-react";

import { Badge, ButtonLink, Card, Section } from "@/components/ui";

const features = [
  {
    title: "대시보드",
    description: "시장 브리핑, 핵심 지표, 히트맵, 강한 셋업을 한 화면에서 먼저 확인합니다.",
    href: "/dashboard",
    icon: BarChart3,
  },
  {
    title: "기회 레이더",
    description: "대표 유니버스에서 다음 거래일과 20거래일 후보를 분리해 읽습니다.",
    href: "/radar",
    icon: Crosshair,
  },
  {
    title: "스크리너",
    description: "조건 기반 필터로 후보를 줄이고, 상세 분석으로 넘어갈 종목을 고릅니다.",
    href: "/screener",
    icon: ListFilter,
  },
  {
    title: "포트폴리오",
    description: "보유 종목, 추천, 이벤트 레이더를 같은 기준으로 비교합니다.",
    href: "/portfolio",
    icon: PieChart,
  },
];

const workflow = [
  {
    title: "시장 신호 수집",
    description: "가격, 거래량, 시장 지표, 일정, 리서치 메타데이터를 분리해 가져옵니다.",
  },
  {
    title: "후보와 분포 계산",
    description: "확률 분포, 방향 확률, 분위수 가격 범위로 판단 재료를 만듭니다.",
  },
  {
    title: "운영 화면에 연결",
    description: "대시보드, 레이더, 종목 상세, 포트폴리오에서 같은 흐름으로 확인합니다.",
  },
];

const limits = [
  {
    title: "수익 보장 없음",
    description: "예측은 매수 지시가 아니라 판단 재료입니다. 확률과 제한을 함께 보여줍니다.",
    icon: ShieldCheck,
  },
  {
    title: "한국 시장 중심",
    description: "현재 운영 범위는 한국 시장 중심이며, 필요한 문맥에서 데이터 범위를 명확히 표시합니다.",
    icon: DatabaseZap,
  },
  {
    title: "부분 실패 대응",
    description: "외부 소스가 늦으면 cached snapshot, quick response, partial 안내를 먼저 사용합니다.",
    icon: Clock3,
  },
];

function ProductPreview() {
  return (
    <div className="rounded-[28px] border border-border/70 bg-white p-3 shadow-[0_32px_100px_-62px_rgba(15,23,42,0.44)] sm:p-4">
      <div className="rounded-[22px] border border-border/70 bg-surface p-4 sm:p-5">
        <div className="flex flex-col gap-3 border-b border-border/70 pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-text-secondary">Dashboard Preview</p>
            <h2 className="mt-1 text-2xl font-bold text-text">오늘 먼저 볼 시장 흐름</h2>
          </div>
          <Badge>partial fallback ready</Badge>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          {["상승 확률", "시장 강도", "리스크"].map((label, index) => (
            <div key={label} className="rounded-[18px] border border-border/70 bg-white p-4">
              <p className="text-sm font-semibold text-text-secondary">{label}</p>
              <p className="mt-3 text-3xl font-bold text-text">
                {index === 0 ? "62%" : index === 1 ? "+1.8" : "중립"}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,0.8fr)]">
          <div className="rounded-[20px] border border-border/70 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-text">기회 후보</p>
              <LineChart size={18} className="text-accent" aria-hidden="true" />
            </div>
            <div className="mt-5 space-y-3">
              {["삼성전자", "SK하이닉스", "현대차"].map((name, index) => (
                <div key={name} className="grid grid-cols-[minmax(0,1fr)_72px_72px] items-center gap-3 text-sm">
                  <span className="truncate font-semibold text-text">{name}</span>
                  <span className="text-right text-text-secondary">{index === 0 ? "5D" : "20D"}</span>
                  <span className="text-right font-semibold text-positive">{index === 2 ? "+1.7%" : "+2.4%"}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[20px] border border-border/70 bg-white p-4">
            <p className="font-semibold text-text">판단 흐름</p>
            <div className="mt-4 space-y-3">
              {["시장 요약", "후보 압축", "포트폴리오 비교"].map((item) => (
                <div key={item} className="flex items-center gap-2 text-sm font-medium text-text-secondary">
                  <CheckCircle2 size={17} className="text-accent" aria-hidden="true" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="landing-page">
      <section className="grid min-h-[calc(100svh-4rem)] items-center gap-10 pb-16 pt-16 lg:grid-cols-[minmax(0,1.02fr)_minmax(420px,0.98fr)] lg:pb-20 lg:pt-20">
        <div className="min-w-0">
          <h1 className="max-w-4xl text-[clamp(2.25rem,10vw,5.75rem)] font-bold leading-[1.04] text-text [overflow-wrap:anywhere]">
            시장 신호를 읽고, 포트폴리오 판단까지 이어갑니다.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-text-secondary sm:text-xl sm:leading-9">
            Stock Predict는 시장 브리핑, 후보 종목, 확률 분포, 포트폴리오 운영을 한 흐름으로 정리하는 투자 분석 서비스입니다.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href="/dashboard" size="lg">
              대시보드 보기
              <ArrowRight size={18} aria-hidden="true" />
            </ButtonLink>
            <ButtonLink href="/radar" size="lg" variant="secondary">
              기회 레이더 보기
            </ButtonLink>
          </div>
        </div>
        <ProductPreview />
      </section>

      <Section id="features">
        <div className="max-w-2xl">
          <h2 className="text-4xl font-bold text-text sm:text-5xl">필요한 화면만 남깁니다.</h2>
          <p className="mt-4 text-lg leading-8 text-text-secondary">
            첫 진입에서는 제품의 목적을 설명하고, 실제 작업은 각 기능 화면에서 바로 이어집니다.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Link key={feature.href} href={feature.href} className="group block">
                <Card className="h-full transition-transform duration-200 group-hover:-translate-y-1">
                  <div className="flex h-12 w-12 items-center justify-center rounded-[16px] bg-accent/10 text-accent">
                    <Icon size={22} aria-hidden="true" />
                  </div>
                  <h3 className="mt-6 text-2xl font-bold text-text">{feature.title}</h3>
                  <p className="mt-3 text-base leading-7 text-text-secondary">{feature.description}</p>
                  <span className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-accent">
                    열기
                    <ArrowRight size={16} aria-hidden="true" />
                  </span>
                </Card>
              </Link>
            );
          })}
        </div>
      </Section>

      <Section id="workflow">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:items-start">
          <div>
            <h2 className="text-4xl font-bold text-text sm:text-5xl">데이터에서 행동까지 짧게.</h2>
            <p className="mt-4 text-lg leading-8 text-text-secondary">
              화면마다 같은 이야기를 반복하지 않고, 시장 탐색에서 운영 판단까지 이어지는 순서를 고정합니다.
            </p>
          </div>
          <div className="space-y-4">
            {workflow.map((step, index) => (
              <Card key={step.title} className="grid gap-4 sm:grid-cols-[72px_minmax(0,1fr)] sm:items-start">
                <div className="flex h-14 w-14 items-center justify-center rounded-[18px] bg-accent text-lg font-bold text-white">
                  {index + 1}
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-text">{step.title}</h3>
                  <p className="mt-2 text-base leading-7 text-text-secondary">{step.description}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </Section>

      <Section>
        <ProductPreview />
      </Section>

      <Section id="limits">
        <div className="rounded-[28px] border border-border/70 bg-surface p-6 sm:p-8 lg:p-10">
          <div className="max-w-2xl">
            <h2 className="text-4xl font-bold text-text sm:text-5xl">좋은 판단은 한계를 같이 봅니다.</h2>
            <p className="mt-4 text-lg leading-8 text-text-secondary">
              예측 숫자는 확률적 판단 재료입니다. 서비스는 데이터 범위와 fallback 상태를 숨기지 않습니다.
            </p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {limits.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title} className="rounded-[22px] border border-border/70 bg-white p-5">
                  <Icon size={23} className="text-accent" aria-hidden="true" />
                  <h3 className="mt-5 text-xl font-bold text-text">{item.title}</h3>
                  <p className="mt-3 text-base leading-7 text-text-secondary">{item.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      <section className="py-12 sm:py-16">
        <div className="rounded-[30px] bg-text px-6 py-10 text-white sm:px-8 lg:px-10">
          <h2 className="max-w-3xl text-4xl font-bold sm:text-5xl">
            지금은 시장을 길게 설명하기보다, 먼저 볼 후보를 정리할 시간입니다.
          </h2>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-white/72">
            대시보드에서 오늘의 흐름을 확인하고, 레이더와 스크리너로 다음 판단 화면으로 이동하세요.
          </p>
          <div className="mt-8">
            <ButtonLink href="/dashboard" size="lg">
              대시보드로 이동
              <ArrowRight size={18} aria-hidden="true" />
            </ButtonLink>
          </div>
        </div>
      </section>
    </div>
  );
}
