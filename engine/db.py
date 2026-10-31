"""Supabase access through its REST API (PostgREST).

Filters use PostgREST syntax, e.g. {"status": "eq.ready", "scheduled_at": "lte.2026-10-20T00:00:00Z"}.
"""
import requests

from engine.config import env


def _headers(extra: dict | None = None) -> dict:
    key = env("SUPABASE_SERVICE_KEY")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # legacy service_role JWT also needs a bearer header
        headers["Authorization"] = f"Bearer {key}"
    return {**headers, **(extra or {})}


def rest_url(path: str = "") -> str:
    return f"{env('SUPABASE_URL').rstrip('/')}/rest/v1/{path}"


def _check(r: requests.Response):
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase error {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


def ping() -> None:
    _check(requests.get(rest_url(), headers=_headers(), timeout=30))


def select(table: str, filters: dict | None = None, columns: str = "*",
           order: str | None = None, limit: int | None = None) -> list[dict]:
    params = {"select": columns, **(filters or {})}
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit
    return _check(requests.get(rest_url(table), headers=_headers(), params=params, timeout=60))


def insert(table: str, rows: list[dict] | dict) -> list[dict]:
    return _check(requests.post(rest_url(table), headers=_headers({"Prefer": "return=representation"}),
                                json=rows, timeout=60))


def upsert(table: str, rows: list[dict] | dict, on_conflict: str) -> list[dict]:
    headers = _headers({"Prefer": "return=representation,resolution=merge-duplicates"})
    return _check(requests.post(rest_url(table), headers=headers, params={"on_conflict": on_conflict},
                                json=rows, timeout=60))


def update(table: str, filters: dict, values: dict) -> list[dict]:
    return _check(requests.patch(rest_url(table), headers=_headers({"Prefer": "return=representation"}),
                                 params=filters, json=values, timeout=60))
