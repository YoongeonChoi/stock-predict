import { get, post } from "@/lib/api/client";
import type {
  DailyBriefingResponse,
  MarketSessionsResponse,
  ResearchArchiveStatus,
  SystemDiagnostics,
} from "@/lib/api";
import type { RequestOptions } from "@/lib/api/shared";

export const systemApi = {
  getResearchArchiveStatus: (refreshIfMissing = false, options?: RequestOptions) =>
    get<ResearchArchiveStatus>(`/api/archive/research/status?refresh_if_missing=${refreshIfMissing}`, options),
  refreshResearchArchive: () => post("/api/archive/research/refresh"),
  getDiagnostics: (options?: RequestOptions) => get<SystemDiagnostics>("/api/diagnostics", options),
  getDailyBriefing: (options?: RequestOptions) => get<DailyBriefingResponse>("/api/briefing/daily", options),
  getMarketSessions: (options?: RequestOptions) => get<MarketSessionsResponse>("/api/market/sessions", options),
};
