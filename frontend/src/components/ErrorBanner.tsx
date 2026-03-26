"use client";

import { ApiError } from "@/lib/api";

const ERROR_GUIDE: Record<string, string> = {
  "SP-1001": "backend/.env 파일에 OPENAI_API_KEY를 설정해 주세요.",
  "SP-1002": "OpenAI API 인증에 실패했습니다. 플랫폼에서 키 상태를 확인해 주세요.",
  "SP-1003": "추가 공공데이터 API를 쓸 경우 해당 키를 backend/.env에 설정해 주세요.",
  "SP-1004": "backend/.env 파일에 ECOS_API_KEY를 설정해 주세요.",
  "SP-1005": "backend/.env 파일에 FMP_API_KEY를 설정해 주세요.",
  "SP-1006": "배포 환경에 Supabase 서버 키를 설정해 주세요.",
  "SP-2001": "추가 공공데이터 API 호출에 실패했습니다. 네트워크 또는 키 상태를 확인해 주세요.",
  "SP-2002": "한국은행 ECOS API 호출에 실패했습니다.",
  "SP-2003": "보조 통계 API 호출에 실패했습니다.",
  "SP-2004": "티커가 없거나 상장폐지되어 외부 시세를 확인하지 못했습니다.",
  "SP-2005": "가격 데이터를 불러오지 못했습니다. 장 상태나 티커를 확인해 주세요.",
  "SP-2006": "FMP API 호출에 실패했습니다.",
  "SP-2007": "뉴스 피드를 불러오지 못했습니다.",
  "SP-2008": "재무 데이터를 불러오지 못했습니다.",
  "SP-3001": "국가 분석 중 데이터 조합에 실패했습니다.",
  "SP-3002": "섹터 분석 중 데이터 조합에 실패했습니다.",
  "SP-3003": "종목 분석 중 데이터 조합에 실패했습니다.",
  "SP-3004": "예측 계산에 필요한 값이 부족합니다.",
  "SP-3005": "뉴스 감성 분석에 실패했습니다.",
  "SP-3006": "점수 계산 중 문제가 발생했습니다.",
  "SP-3007": "과거 유사 국면 예측을 계산하지 못했습니다.",
  "SP-4001": "OpenAI 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
  "SP-4002": "OpenAI 인증에 실패했습니다. API 키 상태를 확인해 주세요.",
  "SP-4003": "AI 분석 결과를 파싱하지 못했습니다.",
  "SP-4004": "OpenAI 응답이 제한 시간 안에 도착하지 않았습니다.",
  "SP-4005": "OpenAI 호출 중 알 수 없는 오류가 발생했습니다.",
  "SP-5001": "데이터베이스 연결에 실패했습니다.",
  "SP-5002": "리포트 아카이브 저장에 실패했습니다.",
  "SP-5003": "워치리스트 처리에 실패했습니다.",
  "SP-5004": "내보내기 파일 생성에 실패했습니다.",
  "SP-5005": "캐시 처리 중 문제가 발생했습니다.",
  "SP-5006": "시스템 진단 정보를 불러오지 못했습니다.",
  "SP-5007": "예측 연구실 데이터를 불러오지 못했습니다.",
  "SP-5008": "포트폴리오 분석에 실패했습니다.",
  "SP-5009": "기관 리서치 아카이브 동기화에 실패했습니다.",
  "SP-5010": "티커 해석에 실패했습니다.",
  "SP-5011": "오늘의 브리핑을 불러오지 못했습니다.",
  "SP-5012": "시장 세션 요약을 불러오지 못했습니다.",
  "SP-5013": "포트폴리오 이벤트 레이더를 불러오지 못했습니다.",
  "SP-5014": "예측 드리프트 데이터를 불러오지 못했습니다.",
  "SP-5015": "조건 추천을 계산하지 못했습니다.",
  "SP-5016": "최적 추천을 계산하지 못했습니다.",
  "SP-5017": "포트폴리오 프로필 저장에 실패했습니다.",
  "SP-5018": "요청이 너무 오래 걸려 이번 응답은 중단되었습니다. 잠시 후 다시 시도해 주세요.",
  "SP-6001": "국가 코드가 올바르지 않습니다.",
  "SP-6002": "섹터 식별자가 올바르지 않습니다.",
  "SP-6003": "기간 파라미터가 올바르지 않습니다.",
  "SP-6004": "비교 대상은 최소 2개 이상이어야 합니다.",
  "SP-6005": "아카이브 항목을 찾을 수 없습니다.",
  "SP-6006": "내보내기 형식이 올바르지 않습니다.",
  "SP-6007": "달력 요청 파라미터가 올바르지 않습니다.",
  "SP-6008": "기관 리서치 아카이브 요청 파라미터가 올바르지 않습니다.",
  "SP-6009": "포트폴리오 보유 종목 입력값이 올바르지 않습니다.",
  "SP-6010": "요청 파라미터나 본문 형식이 올바르지 않습니다.",
  "SP-6011": "요청한 API 경로를 찾을 수 없습니다.",
  "SP-6012": "허용되지 않은 HTTP 메서드입니다.",
  "SP-6013": "포트폴리오 프로필 입력값이 올바르지 않습니다.",
  "SP-6014": "이 작업은 로그인 후 사용할 수 있습니다.",
  "SP-9999": "예상하지 못한 서버 오류가 발생했습니다.",
};

function getGuide(code: string): string {
  return ERROR_GUIDE[code] || "알 수 없는 오류입니다. 잠시 후 다시 시도해 주세요.";
}

interface ErrorBannerProps {
  error: unknown;
  onRetry?: () => void;
}

export default function ErrorBanner({ error, onRetry }: ErrorBannerProps) {
  const isApiError = error instanceof ApiError;
  const code = isApiError ? error.errorCode : "";
  const message = isApiError ? error.message : error instanceof Error ? error.message : String(error);
  const detail = isApiError ? error.detail : "";
  const guide = code ? getGuide(code) : "";
  const primaryMessage = guide || message;
  const secondaryMessage = guide && guide !== message ? message : "";

  return (
    <div className="card border-negative/30 bg-negative/5">
      <div className="flex items-start gap-3">
        <div className="text-negative text-lg shrink-0 mt-0.5">!</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-negative text-sm">오류가 발생했습니다</h3>
            {code ? <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-negative/10 text-negative">{code}</span> : null}
          </div>
          <p className="text-sm text-text">{primaryMessage}</p>
          {secondaryMessage ? <p className="text-xs text-text-secondary mt-1">원본 메시지: {secondaryMessage}</p> : null}
          {detail ? <p className="text-xs text-text-secondary mt-1">세부 정보: {detail}</p> : null}
        </div>
        {onRetry ? (
          <button onClick={onRetry} className="px-3 py-1.5 bg-accent text-white rounded-lg text-xs shrink-0 hover:bg-accent/80 transition-colors">
            다시 시도
          </button>
        ) : null}
      </div>
    </div>
  );
}

interface WarningBannerProps {
  codes: string[];
}

export function WarningBanner({ codes }: WarningBannerProps) {
  if (!codes || codes.length === 0) return null;

  return (
    <div className="card border-warning/30 bg-warning/5">
      <div className="flex items-start gap-3">
        <div className="text-warning text-lg shrink-0">!</div>
        <div className="flex-1">
          <p className="text-sm text-warning font-medium mb-1">일부 데이터가 제한적으로 제공됩니다</p>
          <div className="space-y-1">
            {codes.map((code) => (
              <div key={code} className="flex items-center gap-2 text-xs text-text-secondary">
                <span className="font-mono px-1 py-0.5 rounded bg-warning/10 text-warning">{code}</span>
                <span>{getGuide(code)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
