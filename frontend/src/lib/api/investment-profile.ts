"use client";

import { get, post, put } from "@/lib/api/client";
import type {
  InvestmentProfile,
  InvestmentProfileOptionsResponse,
  InvestmentProfileResolveRequest,
  InvestmentProfileResolveResponse,
  InvestmentProfileUpdateRequest,
} from "@/lib/api/types";

export const investmentProfileApi = {
  getInvestmentProfile: () => get<InvestmentProfile>("/api/investment-profile"),
  updateInvestmentProfile: (data: InvestmentProfileUpdateRequest) =>
    put<InvestmentProfile>("/api/investment-profile", data),
  getInvestmentProfileOptions: () =>
    get<InvestmentProfileOptionsResponse>("/api/investment-profile/options"),
  resolveInvestmentProfile: (data: InvestmentProfileResolveRequest) =>
    post<InvestmentProfileResolveResponse>("/api/investment-profile/resolve", data),
};
