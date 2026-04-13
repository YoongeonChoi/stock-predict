export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export interface StockDetailRequestOptions extends RequestOptions {
  preferFull?: boolean;
}

