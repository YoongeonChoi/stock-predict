from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings


class SupabaseConfigError(RuntimeError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_response_rows(payload: Any) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [dict(payload)]
    return []


class SupabaseClient:
    def __init__(self):
        self._settings = get_settings()

    @property
    def _base_url(self) -> str:
        value = self._settings.supabase_url.strip().rstrip("/")
        if not value:
            raise SupabaseConfigError("SUPABASE_URL is not configured")
        return value

    @property
    def _server_key(self) -> str:
        value = self._settings.supabase_server_key.strip()
        if not value:
            raise SupabaseConfigError("SUPABASE_SERVER_KEY is not configured")
        return value

    def _service_headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._server_key,
            "Authorization": f"Bearer {self._server_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "apikey": self._server_key,
            "Authorization": f"Bearer {access_token}",
        }

    def _admin_headers(self) -> dict[str, str]:
        return {
            "apikey": self._server_key,
            "Authorization": f"Bearer {self._server_key}",
            "Content-Type": "application/json",
        }

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json: Any = None,
        allow_unauthorized: bool = False,
    ) -> Any:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=20.0) as client:
            response = await client.request(
                method,
                path,
                headers=headers,
                params=params,
                json=json,
            )

        if allow_unauthorized and response.status_code in {401, 403}:
            return None

        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    async def get_user(self, access_token: str) -> dict[str, Any] | None:
        payload = await self._request_json(
            "GET",
            "/auth/v1/user",
            headers=self._auth_headers(access_token),
            allow_unauthorized=True,
        )
        return dict(payload) if isinstance(payload, dict) else None

    async def admin_list_users(self, *, page: int = 1, per_page: int = 200) -> list[dict]:
        payload = await self._request_json(
            "GET",
            "/auth/v1/admin/users",
            headers=self._admin_headers(),
            params={"page": page, "per_page": per_page},
        )
        if isinstance(payload, dict):
            rows = payload.get("users")
            if isinstance(rows, list):
                return [dict(item) for item in rows if isinstance(item, dict)]
        return []

    async def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        normalized = username.strip().lower()
        if not normalized:
            return None

        for page in range(1, 11):
            users = await self.admin_list_users(page=page, per_page=200)
            if not users:
                return None
            for user in users:
                metadata = user.get("user_metadata")
                if not isinstance(metadata, dict):
                    metadata = user.get("raw_user_meta_data")
                if not isinstance(metadata, dict):
                    metadata = {}
                value = metadata.get("username")
                if isinstance(value, str) and value.strip().lower() == normalized:
                    return user
            if len(users) < 200:
                return None
        return None

    async def admin_update_user_metadata(self, user_id: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
        payload = await self._request_json(
            "PUT",
            f"/auth/v1/admin/users/{user_id}",
            headers=self._admin_headers(),
            json={"user_metadata": metadata},
        )
        return dict(payload) if isinstance(payload, dict) else None

    async def watchlist_list(self, user_id: str) -> list[dict]:
        payload = await self._request_json(
            "GET",
            "/rest/v1/watchlist",
            headers=self._service_headers(),
            params={
                "select": "id,ticker,country_code,added_at",
                "user_id": f"eq.{user_id}",
                "order": "added_at.desc",
            },
        )
        return _normalize_response_rows(payload)

    async def watchlist_add(self, user_id: str, ticker: str, country_code: str) -> dict:
        payload = await self._request_json(
            "POST",
            "/rest/v1/watchlist",
            headers=self._service_headers(
                prefer="resolution=merge-duplicates,return=representation",
            ),
            params={"on_conflict": "user_id,ticker"},
            json={
                "user_id": user_id,
                "ticker": ticker,
                "country_code": country_code,
            },
        )
        rows = _normalize_response_rows(payload)
        return rows[0] if rows else {
            "user_id": user_id,
            "ticker": ticker,
            "country_code": country_code,
        }

    async def watchlist_update(
        self,
        item_id: int,
        user_id: str,
        ticker: str,
        country_code: str,
    ) -> None:
        await self._request_json(
            "PATCH",
            "/rest/v1/watchlist",
            headers=self._service_headers(prefer="return=minimal"),
            params={"id": f"eq.{item_id}", "user_id": f"eq.{user_id}"},
            json={"ticker": ticker, "country_code": country_code},
        )

    async def watchlist_remove(self, user_id: str, ticker: str) -> None:
        await self._request_json(
            "DELETE",
            "/rest/v1/watchlist",
            headers=self._service_headers(prefer="return=minimal"),
            params={"user_id": f"eq.{user_id}", "ticker": f"eq.{ticker}"},
        )

    async def portfolio_list(self, user_id: str) -> list[dict]:
        payload = await self._request_json(
            "GET",
            "/rest/v1/portfolio_holdings",
            headers=self._service_headers(),
            params={
                "select": "id,ticker,name,country_code,buy_price,quantity,buy_date,created_at",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
        )
        return _normalize_response_rows(payload)

    async def portfolio_add(
        self,
        user_id: str,
        ticker: str,
        name: str,
        country_code: str,
        buy_price: float,
        quantity: float,
        buy_date: str,
    ) -> dict:
        payload = await self._request_json(
            "POST",
            "/rest/v1/portfolio_holdings",
            headers=self._service_headers(prefer="return=representation"),
            json={
                "user_id": user_id,
                "ticker": ticker,
                "name": name,
                "country_code": country_code,
                "buy_price": buy_price,
                "quantity": quantity,
                "buy_date": buy_date,
            },
        )
        rows = _normalize_response_rows(payload)
        return rows[0] if rows else {}

    async def portfolio_update(
        self,
        user_id: str,
        holding_id: int,
        ticker: str,
        name: str,
        country_code: str,
        buy_price: float,
        quantity: float,
        buy_date: str,
    ) -> None:
        await self._request_json(
            "PATCH",
            "/rest/v1/portfolio_holdings",
            headers=self._service_headers(prefer="return=minimal"),
            params={"id": f"eq.{holding_id}", "user_id": f"eq.{user_id}"},
            json={
                "ticker": ticker,
                "name": name,
                "country_code": country_code,
                "buy_price": buy_price,
                "quantity": quantity,
                "buy_date": buy_date,
            },
        )

    async def portfolio_update_identity(
        self,
        user_id: str,
        holding_id: int,
        ticker: str,
        country_code: str,
    ) -> None:
        await self._request_json(
            "PATCH",
            "/rest/v1/portfolio_holdings",
            headers=self._service_headers(prefer="return=minimal"),
            params={"id": f"eq.{holding_id}", "user_id": f"eq.{user_id}"},
            json={"ticker": ticker, "country_code": country_code},
        )

    async def portfolio_delete(self, user_id: str, holding_id: int) -> None:
        await self._request_json(
            "DELETE",
            "/rest/v1/portfolio_holdings",
            headers=self._service_headers(prefer="return=minimal"),
            params={"id": f"eq.{holding_id}", "user_id": f"eq.{user_id}"},
        )

    async def portfolio_profile_get(self, user_id: str) -> dict:
        payload = await self._request_json(
            "GET",
            "/rest/v1/portfolio_profile",
            headers=self._service_headers(),
            params={
                "select": "user_id,total_assets,cash_balance,monthly_budget,updated_at",
                "user_id": f"eq.{user_id}",
            },
        )
        rows = _normalize_response_rows(payload)
        if rows:
            return rows[0]
        return {
            "user_id": user_id,
            "total_assets": 0.0,
            "cash_balance": 0.0,
            "monthly_budget": 0.0,
            "updated_at": _utcnow_iso(),
        }

    async def portfolio_profile_upsert(
        self,
        user_id: str,
        total_assets: float,
        cash_balance: float,
        monthly_budget: float,
    ) -> dict:
        payload = await self._request_json(
            "POST",
            "/rest/v1/portfolio_profile",
            headers=self._service_headers(
                prefer="resolution=merge-duplicates,return=representation",
            ),
            params={"on_conflict": "user_id"},
            json={
                "user_id": user_id,
                "total_assets": total_assets,
                "cash_balance": cash_balance,
                "monthly_budget": monthly_budget,
                "updated_at": _utcnow_iso(),
            },
        )
        rows = _normalize_response_rows(payload)
        return rows[0] if rows else {
            "user_id": user_id,
            "total_assets": total_assets,
            "cash_balance": cash_balance,
            "monthly_budget": monthly_budget,
            "updated_at": _utcnow_iso(),
        }


supabase_client = SupabaseClient()
