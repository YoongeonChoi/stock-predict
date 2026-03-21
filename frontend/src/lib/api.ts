const API = process.env.NEXT_PUBLIC_API_URL || "";

export interface ApiErrorInfo {
  error_code: string;
  message: string;
  detail?: string;
}

export class ApiError extends Error {
  status: number;
  errorCode: string;
  detail: string;

  constructor(status: number, info: ApiErrorInfo) {
    super(info.message);
    this.status = status;
    this.errorCode = info.error_code || `HTTP-${status}`;
    this.detail = info.detail || "";
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

async function post(path: string, body?: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

async function del(path: string) {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok) {
    let info: ApiErrorInfo;
    try {
      info = await res.json();
    } catch {
      info = { error_code: `HTTP-${res.status}`, message: res.statusText };
    }
    throw new ApiError(res.status, info);
  }
  return res.json();
}

export const api = {
  getCountries: () => get<import("./types").CountryListItem[]>("/api/countries"),
  getCountryReport: (code: string) => get<import("./types").CountryReport>(`/api/country/${code}/report`),
  getCountryForecast: (code: string) => get<import("./types").IndexForecast>(`/api/country/${code}/forecast`),
  getSectors: (code: string) => get<import("./types").SectorListItem[]>(`/api/country/${code}/sectors`),
  getSectorReport: (code: string, sectorId: string) =>
    get<import("./types").SectorReport>(`/api/country/${code}/sector/${sectorId}/report`),
  getStockDetail: (ticker: string) => get<import("./types").StockDetail>(`/api/stock/${ticker}/detail`),
  getStockChart: (ticker: string, period = "3mo") =>
    get<{ data: import("./types").PricePoint[] }>(`/api/stock/${ticker}/chart?period=${period}`),
  getWatchlist: () => get<import("./types").WatchlistItem[]>("/api/watchlist"),
  addWatchlist: (ticker: string, country_code = "US") => post(`/api/watchlist/${ticker}?country_code=${country_code}`),
  removeWatchlist: (ticker: string) => del(`/api/watchlist/${ticker}`),
  compare: (tickers: string[]) => get<unknown[]>(`/api/compare?tickers=${tickers.join(",")}`),
  getArchive: () => get<unknown[]>("/api/archive"),
  getArchiveDetail: (id: number) => get<unknown>(`/api/archive/${id}`),
  getCalendar: (code: string) => get<unknown>(`/api/calendar/${code}`),
};
