import { cn } from "@/lib/utils";

interface ModelOutputNoticeProps {
  className?: string;
  compact?: boolean;
}

export default function ModelOutputNotice({ className, compact = false }: ModelOutputNoticeProps) {
  return (
    <div className={cn("ui-panel-muted text-text-secondary", compact ? "text-xs leading-5" : "text-sm leading-6", className)}>
      조건부 분포와 포트폴리오 제약을 함께 본 참고 신호입니다. 수익 보장이나 즉시 매수 지시가 아니며, 예측 연구실의 검증 표본과 리스크 플래그를 함께 확인하세요.
    </div>
  );
}
