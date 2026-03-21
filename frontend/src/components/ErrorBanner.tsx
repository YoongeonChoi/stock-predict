"use client";

import { ApiError } from "@/lib/api";

const ERROR_GUIDE: Record<string, string> = {
  "SP-1001": "backend/.env 파일에 OPENAI_API_KEY를 설정하세요.",
  "SP-1002": "OpenAI API 키가 잘못되었습니다. platform.openai.com에서 확인하세요.",
  "SP-1003": "backend/.env 파일에 FRED_API_KEY를 설정하세요 (무료).",
  "SP-1004": "backend/.env 파일에 ECOS_API_KEY를 설정하세요 (무료).",
  "SP-1005": "backend/.env 파일에 FMP_API_KEY를 설정하세요 (무료, 선택).",
  "SP-2001": "FRED API 요청 실패. API 키 또는 네트워크를 확인하세요.",
  "SP-2002": "한국은행 ECOS API 요청 실패.",
  "SP-2003": "일본은행 BOJ API 요청 실패.",
  "SP-2004": "티커를 찾을 수 없거나 상장폐지되었습니다.",
  "SP-2005": "가격 데이터를 가져올 수 없습니다.",
  "SP-2006": "FMP API 요청 실패.",
  "SP-2007": "뉴스 피드를 가져올 수 없습니다.",
  "SP-3001": "국가 분석 중 오류가 발생했습니다.",
  "SP-3002": "섹터 분석 중 오류가 발생했습니다.",
  "SP-3003": "종목 분석 중 오류가 발생했습니다.",
  "SP-3004": "지수 예측 엔진 오류.",
  "SP-4001": "OpenAI 사용량 한도 초과. 결제 정보를 확인하세요.",
  "SP-4002": "OpenAI 인증 실패. API 키를 확인하세요.",
  "SP-4003": "AI 응답 파싱 오류.",
  "SP-4004": "AI 요청 시간 초과.",
  "SP-5001": "데이터베이스 연결 오류.",
  "SP-5002": "리포트 저장 실패.",
  "SP-5003": "워치리스트 작업 실패.",
  "SP-5004": "내보내기 생성 실패.",
  "SP-6001": "지원하지 않는 국가입니다.",
  "SP-6002": "존재하지 않는 섹터입니다.",
  "SP-6003": "유효하지 않은 기간 파라미터입니다.",
  "SP-6004": "비교를 위해 최소 2개 티커가 필요합니다.",
  "SP-6005": "해당 리포트를 찾을 수 없습니다.",
  "SP-6006": "지원하지 않는 내보내기 형식입니다.",
  "SP-9999": "예상치 못한 서버 오류가 발생했습니다.",
};

function getGuide(code: string): string {
  return ERROR_GUIDE[code] || "알 수 없는 오류입니다. 로그를 확인하세요.";
}

interface ErrorBannerProps {
  error: unknown;
  onRetry?: () => void;
}

export default function ErrorBanner({ error, onRetry }: ErrorBannerProps) {
  const isApiError = error instanceof ApiError;
  const code = isApiError ? error.errorCode : "";
  const message = isApiError ? error.message : (error instanceof Error ? error.message : String(error));
  const detail = isApiError ? error.detail : "";
  const guide = code ? getGuide(code) : "";

  return (
    <div className="card border-negative/30 bg-negative/5">
      <div className="flex items-start gap-3">
        <div className="text-negative text-lg shrink-0 mt-0.5">✕</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-negative text-sm">Error</h3>
            {code && (
              <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-negative/10 text-negative">{code}</span>
            )}
          </div>
          <p className="text-sm text-text">{message}</p>
          {detail && <p className="text-xs text-text-secondary mt-1">{detail}</p>}
          {guide && <p className="text-xs text-text-secondary mt-1 italic">{guide}</p>}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-3 py-1.5 bg-accent text-white rounded-lg text-xs shrink-0 hover:bg-accent/80 transition-colors"
          >
            Retry
          </button>
        )}
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
        <div className="text-warning text-lg shrink-0">⚠</div>
        <div className="flex-1">
          <p className="text-sm text-warning font-medium mb-1">일부 기능을 사용할 수 없습니다</p>
          <div className="space-y-1">
            {codes.map((c) => (
              <div key={c} className="flex items-center gap-2 text-xs text-text-secondary">
                <span className="font-mono px-1 py-0.5 rounded bg-warning/10 text-warning">{c}</span>
                <span>{getGuide(c)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
