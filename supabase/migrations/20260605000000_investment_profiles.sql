CREATE TABLE IF NOT EXISTS public.investment_profiles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

  profile_code TEXT NOT NULL
    CHECK (profile_code IN (
      'capital_preservation',
      'conservative',
      'balanced',
      'growth',
      'aggressive'
    )),

  risk_tolerance SMALLINT NOT NULL CHECK (risk_tolerance BETWEEN 1 AND 5),

  investment_horizon TEXT NOT NULL
    CHECK (investment_horizon IN ('short', 'swing', 'medium', 'long')),

  max_drawdown_pct NUMERIC NOT NULL,

  turnover_preference TEXT NOT NULL
    CHECK (turnover_preference IN ('low', 'medium', 'high')),

  concentration_preference TEXT NOT NULL
    CHECK (concentration_preference IN ('low', 'medium', 'high')),

  cash_buffer_min_pct NUMERIC NOT NULL,
  cash_buffer_max_pct NUMERIC NOT NULL,

  policy_version TEXT NOT NULL DEFAULT 'investment-policy-v1',
  questionnaire_json JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.investment_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS investment_profiles_select_own ON public.investment_profiles;
CREATE POLICY investment_profiles_select_own
ON public.investment_profiles
FOR SELECT
USING (auth.uid() = user_id);

DROP POLICY IF EXISTS investment_profiles_insert_own ON public.investment_profiles;
CREATE POLICY investment_profiles_insert_own
ON public.investment_profiles
FOR INSERT
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS investment_profiles_update_own ON public.investment_profiles;
CREATE POLICY investment_profiles_update_own
ON public.investment_profiles
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS investment_profiles_delete_own ON public.investment_profiles;
CREATE POLICY investment_profiles_delete_own
ON public.investment_profiles
FOR DELETE
USING (auth.uid() = user_id);

CREATE TABLE IF NOT EXISTS public.portfolio_recommendation_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  profile_code TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  portfolio_state_hash TEXT NOT NULL,

  recommendation_type TEXT NOT NULL
    CHECK (recommendation_type IN ('conditional', 'optimal', 'personalized')),

  request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  response_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  recommended_items_json JSONB NOT NULL DEFAULT '[]'::jsonb,

  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.portfolio_recommendation_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS portfolio_recommendation_snapshots_select_own ON public.portfolio_recommendation_snapshots;
CREATE POLICY portfolio_recommendation_snapshots_select_own
ON public.portfolio_recommendation_snapshots
FOR SELECT
USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS portfolio_recommendation_snapshots_user_generated_idx
ON public.portfolio_recommendation_snapshots (user_id, generated_at DESC);
