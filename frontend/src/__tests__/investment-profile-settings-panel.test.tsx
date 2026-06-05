import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InvestmentProfileSettingsPanel from "@/components/settings/InvestmentProfileSettingsPanel";
import { api } from "@/lib/api";

const mockSession = { user: { id: "user-123" } };

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({
    loading: false,
    session: mockSession,
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getInvestmentProfile: vi.fn(),
      updateInvestmentProfile: vi.fn(),
      getInvestmentProfileOptions: vi.fn(),
    },
  };
});

const options = [
  {
    profile_code: "balanced",
    profile_label: "균형형",
    description: "수익과 리스크를 균형 있게 반영합니다.",
    risk_tolerance: 3,
    recommended_equity_pct: 82,
    cash_buffer_pct: 18,
    max_single_weight_pct: 14.5,
    optimization_style: "balanced",
  },
  {
    profile_code: "growth",
    profile_label: "성장추구형",
    description: "기대초과수익과 상승 확률을 더 중시합니다.",
    risk_tolerance: 4,
    recommended_equity_pct: 90,
    cash_buffer_pct: 10,
    max_single_weight_pct: 17.5,
    optimization_style: "offensive",
  },
] as const;

describe("InvestmentProfileSettingsPanel", () => {
  afterEach(() => {
    vi.mocked(api.getInvestmentProfile).mockReset();
    vi.mocked(api.updateInvestmentProfile).mockReset();
    vi.mocked(api.getInvestmentProfileOptions).mockReset();
  });

  it("renders profile options and saves the selected code", async () => {
    vi.mocked(api.getInvestmentProfile).mockResolvedValue({
      profile_code: "balanced",
      profile_label: "균형형",
      risk_tolerance: 3,
      investment_horizon: "medium",
      max_drawdown_pct: 15,
      turnover_preference: "medium",
      concentration_preference: "medium",
      cash_buffer_min_pct: 10,
      cash_buffer_max_pct: 25,
      policy_version: "investment-policy-v1",
      questionnaire_json: {},
      updated_at: null,
      persisted: false,
    });
    vi.mocked(api.getInvestmentProfileOptions).mockResolvedValue({
      policy_version: "investment-policy-v1",
      options: [...options],
    });
    vi.mocked(api.updateInvestmentProfile).mockResolvedValue({
      profile_code: "growth",
      profile_label: "성장추구형",
      risk_tolerance: 4,
      investment_horizon: "long",
      max_drawdown_pct: 22,
      turnover_preference: "medium",
      concentration_preference: "medium",
      cash_buffer_min_pct: 6,
      cash_buffer_max_pct: 18,
      policy_version: "investment-policy-v1",
      questionnaire_json: {},
      updated_at: "2026-06-05T00:00:00Z",
      persisted: true,
    });

    render(<InvestmentProfileSettingsPanel />);

    expect(await screen.findByRole("heading", { name: "투자 성향" })).toBeInTheDocument();
    expect(screen.getByText("기본값")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/성장추구형/));
    fireEvent.click(screen.getByRole("button", { name: "투자 성향 저장" }));

    await waitFor(() => {
      expect(api.updateInvestmentProfile).toHaveBeenCalledWith({ profile_code: "growth" });
    });
  });
});
