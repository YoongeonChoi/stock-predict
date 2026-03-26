"use client";

import { ApiError } from "@/lib/api";

const ERROR_GUIDE: Record<string, string> = {
  "SP-1001": "backend/.env 파일에 OPENAI_API_KEY를 설정해 주세요.",
  "SP-1002": "OpenAI API 인증에 실패했습니다. 플랫폼에서 키 상태를 확인해 주세요.",
  "SP-1003": "추가 공공데이터 API를 쓸 경우 해당 키를 backend/.env에 설정해 주세요.",
  "SP-1004": "backend/.env 파일에 ECOS_API_KEY를 설정해 주세요.",
  "SP-1005": "backend/.env 파일에 FMP_API_KEY를 설정해 주세요.",
  "SP-2001": "추가 공공데이터 API 호출에 실패했습니다. 네트워크 또는 키 상태를 확인해 주세요.",
  "SP-2002": "한국은행 ECOS API 호출에 실패했습니다.",
  "SP-2003": "보조 통계 API 호출에 실패했습니다.",
  "SP-2004": "시장 데이터를 가져오는 중 외부 응답이 비정상이었습니다.",
  "SP-2005": "뉴스 데이터를 불러오지 못했습니다.",
  "SP-2006": "FMP API 호출에 실패했습니다.",
  "SP-2007": "외부 리포트 소스를 읽는 중 문제가 발생했습니다.",
  "SP-3001": "국가 분석 중 데이터 조합에 실패했습니다.",
  "SP-3002": "섹터 분석 중 데이터 조합에 실패했습니다.",
  "SP-3003": "종목 분석 중 데이터 조합에 실패했습니다.",
  "SP-3004": "예측 계산에 필요한 값이 부족합니다.",
  "SP-4001": "OpenAI 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
  "SP-4002": "OpenAI 요청 제한에 걸렸습니다. 잠시 후 다시 시도해 주세요.",
  "SP-4003": "AI 분석 결과를 파싱하지 못했습니다.",
  "SP-4004": "AI 출력 검증에 실패했습니다.",
  "SP-5001": "보고서 저장 중 오류가 발생했습니다.",
  "SP-5002": "감시 목록을 불러오지 못했습니다.",
  "SP-5003": "내보내기 파일 생성에 실패했습니다.",
  "SP-5004": "아카이브 조회에 실패했습니다.",
  "SP-5006": "시스템 진단 정보를 불러오지 못했습니다.",
  "SP-5007": "예측 연구실 데이터를 불러오지 못했습니다.",
  "SP-5008": "포트폴리오 분석에 실패했습니다.",
  "SP-5009": "기관 리서치 아카이브 동기화에 실패했습니다.",
  "SP-6001": "국가 코드가 올바르지 않습니다.",
  "SP-6002": "티커 형식이 올바르지 않습니다.",
  "SP-6003": "요청 형식이 잘못되었습니다.",
  "SP-6004": "비교 대상은 최소 2개 이상이어야 합니다.",
  "SP-6005": "아카이브 항목을 찾을 수 없습니다.",
  "SP-6006": "달력 요청 파라미터가 올바르지 않습니다.",
  "SP-6008": "기관 리서치 아카이브 요청 파라미터가 올바르지 않습니다.",
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
