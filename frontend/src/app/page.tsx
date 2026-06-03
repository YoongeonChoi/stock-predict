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
    description: "브리핑, 핵심 지표, 히트맵, 강한 셋업을 같은 화면에 배치합니다.",
    href: "/dashboard",
    icon: BarChart3,
  },
  {
    title: "기회 레이더",
    description: "대표 유니버스에서 다음 거래일 후보와 20거래일 후보를 구분해 표시합니다.",
    href: "/radar",
    icon: Crosshair,
  },
  {
    title: "스크리너",
    description: "조건 기반 필터로 티커 목록을 줄이고 상세 화면으로 연결합니다.",
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
    title: "시장 데이터",
    description: "지수, 종목, 거래량, 일정, 리서치 메타데이터를 분리해 수집합니다.",
  },
  {
    title: "예측 분포",
    description: "방향 확률, 기대 수익률, 가격 분위수를 종목별로 계산합니다.",
  },
  {
    title: "포트폴리오 비교",
    description: "보유 종목과 후보를 같은 기준으로 비교합니다.",
  },
];

const limits = [
  {
    title: "수익 보장 없음",
    description: "매수 지시가 아니라 확률, 손익비, 위험 구간을 함께 표시합니다.",
    icon: ShieldCheck,
  },
  {
    title: "한국 시장 중심",
    description: "현재 운영 범위는 한국 시장이며, 데이터 범위는 화면별로 분리해 표시합니다.",
    icon: DatabaseZap,
  },
  {
    title: "부분 실패 대응",
    description: "외부 응답이 늦으면 마지막 스냅샷과 partial 상태를 표시합니다.",
    icon: Clock3,
  },
];

function ProductPreview() {
  return (
    <div className="landing-product-preview rounded-[28px] border border-border/70 bg-white p-3 shadow-[0_32px_100px_-62px_rgba(15,23,42,0.44)] sm:p-4">
      <div className="rounded-[22px] border border-border/70 bg-surface p-4 sm:p-5">
        <div className="flex min-w-0 flex-col gap-3 border-b border-border/70 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-text-secondary">Dashboard</p>
            <h2 className="mt-1 text-2xl font-bold text-text">시장 요약</h2>
          </div>
          <Badge className="max-w-full whitespace-normal text-left leading-5">partial fallback ready</Badge>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {["상승 확률", "시장 강도", "리스크"].map((label, index) => (
            <div key={label} className="min-w-0 rounded-[18px] border border-border/70 bg-white p-4">
              <p className="text-sm font-semibold text-text-secondary">{label}</p>
              <p className="landing-preview-metric-value mt-3 text-3xl font-bold text-text">
                {index === 0 ? "62%" : index === 1 ? "+1.8" : "중립"}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-4 grid gap-4">
          <div className="rounded-[20px] border border-border/70 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-text">기회 후보</p>
              <LineChart size={18} className="text-accent" aria-hidden="true" />
            </div>
            <div className="mt-5 space-y-3">
              {["삼성전자", "SK하이닉스", "현대차"].map((name, index) => (
                <div key={name} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 text-sm">
                  <span className="min-w-0 font-semibold text-text">{name}</span>
                  <span className="text-right text-text-secondary">{index === 0 ? "5D" : "20D"}</span>
                  <span className="text-right font-semibold text-positive">{index === 2 ? "+1.7%" : "+2.4%"}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[20px] border border-border/70 bg-white p-4">
            <p className="font-semibold text-text">연결 화면</p>
            <div className="mt-4 space-y-3">
              {["시장 요약", "후보 목록", "포트폴리오"].map((item) => (
                <div key={item} className="flex items-center gap-2 text-sm font-medium text-text-secondary">
                  <CheckCircle2 size={17} className="shrink-0 text-accent" aria-hidden="true" />
                  <span className="min-w-0">{item}</span>
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
      <section className="landing-hero grid items-center gap-10 pb-14 pt-12 lg:grid-cols-[minmax(0,0.95fr)_minmax(360px,0.85fr)] lg:gap-12 lg:pb-16 lg:pt-16 xl:grid-cols-[minmax(0,0.9fr)_minmax(420px,0.82fr)]">
        <div className="min-w-0">
          <h1 className="landing-hero-title text-5xl font-bold leading-[1.1] text-text sm:text-6xl lg:text-7xl">
            Stock Predict
          </h1>
          <p className="landing-hero-copy mt-7 max-w-2xl text-lg leading-8 text-text-secondary sm:text-xl sm:leading-9">
            한국 시장 브리핑, 기회 레이더, 스크리너, 포트폴리오 비교를 제공합니다.
          </p>
          <div className="mt-9 flex min-w-0 flex-col gap-3 sm:flex-row">
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
          <h2 className="text-4xl font-bold text-text sm:text-5xl">주요 화면</h2>
          <p className="mt-4 text-lg leading-8 text-text-secondary">
            대시보드, 기회 레이더, 스크리너, 포트폴리오 화면으로 바로 이동합니다.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Link key={feature.href} href={feature.href} className="group block min-w-0">
                <Card className="h-full min-w-0 transition-transform duration-200 group-hover:-translate-y-1">
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
            <h2 className="text-4xl font-bold text-text sm:text-5xl">분석 순서</h2>
            <p className="mt-4 text-lg leading-8 text-text-secondary">
              수집, 계산, 비교 순서로 화면을 나눕니다.
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
            <h2 className="text-4xl font-bold text-text sm:text-5xl">운영 기준</h2>
            <p className="mt-4 text-lg leading-8 text-text-secondary">
              예측 수치, 데이터 범위, fallback 상태를 화면 안에 표시합니다.
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
            현재 시장 대시보드
          </h2>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-white/72">
            시장 요약, 레이더 후보, 스크리너 조건을 같은 기준으로 확인합니다.
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
