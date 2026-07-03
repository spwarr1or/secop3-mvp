from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from clean_data import normalize_key
from config import DATASETS, RAW_DIR, SOCRATA_APP_TOKEN


def _headers() -> dict[str, str]:
    headers = {"User-Agent": "secop3-mvp/0.2 public-data-analysis"}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN
    return headers


def _variants(value: str) -> list[str]:
    key = normalize_key(value)
    title = value.strip()
    no_accents = key.title()
    return list(dict.fromkeys([title, no_accents, key, key.upper()]))


def build_exact_where(city_col: str, department_col: str, municipio: str, departamento: str) -> str:
    cities = _variants(municipio)
    departments = _variants(departamento)
    city_filter = " OR ".join(f"`{city_col}` = '{city}'" for city in cities)
    department_filter = " OR ".join(f"`{department_col}` = '{dept}'" for dept in departments)
    return f"({city_filter}) AND ({department_filter})"


def build_flexible_where(entity_col: str, department_col: str, municipio: str, departamento: str) -> str:
    city_key = normalize_key(municipio)
    dept_key = normalize_key(departamento)
    return (
        f"upper(`{entity_col}`) like '%{city_key}%' "
        f"AND upper(`{department_col}`) like '%{dept_key}%'"
    )


def fetch_dataset(dataset_id: str, filters: dict[str, Any] | None = None, limit: int = 50000) -> pd.DataFrame:
    """Download a Socrata dataset using $limit/$offset pagination and persist the raw rows."""
    filters = filters or {}
    endpoint = f"https://www.datos.gov.co/resource/{dataset_id}.json"
    page_size = min(int(filters.get("$limit", 5000)), 50000)
    max_rows = int(limit)
    offset = 0
    rows: list[dict[str, Any]] = []
    had_error = False

    while offset < max_rows:
        params = {k: v for k, v in filters.items() if v not in (None, "")}
        params["$limit"] = min(page_size, max_rows - offset)
        params["$offset"] = offset
        try:
            response = requests.get(endpoint, params=params, headers=_headers(), timeout=45)
            response.raise_for_status()
            batch = response.json()
        except requests.RequestException as exc:
            print(f"[WARN] Error de conexión descargando {dataset_id}: {exc}")
            had_error = True
            break
        except ValueError as exc:
            print(f"[WARN] Respuesta no JSON para {dataset_id}: {exc}")
            had_error = True
            break

        if not batch:
            break

        rows.extend(batch)
        offset += len(batch)
        print(f"{dataset_id}: {len(rows)} registros descargados")

        if len(batch) < params["$limit"]:
            break
        time.sleep(0.15)

    if had_error and not rows:
        fallback = _latest_non_empty_raw(dataset_id)
        if fallback:
            print(f"[WARN] Usando respaldo crudo previo para {dataset_id}: {fallback}")
            return pd.DataFrame(json.loads(fallback.read_text(encoding="utf-8")))

    raw_path = RAW_DIR / f"{dataset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{dataset_id}: descarga finalizada con {len(rows)} registros. Raw: {raw_path}")
    return pd.DataFrame(rows)


def _latest_non_empty_raw(dataset_id: str) -> Path | None:
    candidates = sorted(RAW_DIR.glob(f"{dataset_id}_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rows, list) and rows:
            return path
    return None


def fetch_target_dataset(kind: str, municipio: str, departamento: str, limit: int = 50000) -> pd.DataFrame:
    dataset = DATASETS[kind]
    exact_where = build_exact_where(dataset["city_col"], dataset["department_col"], municipio, departamento)
    df = fetch_dataset(dataset["id"], {"$where": exact_where}, limit=limit)
    if not df.empty:
        return df

    print(f"{kind}: sin resultados exactos; se activa búsqueda flexible por entidad y departamento.")
    flexible_where = build_flexible_where(dataset["entity_col"], dataset["department_col"], municipio, departamento)
    return fetch_dataset(dataset["id"], {"$where": flexible_where}, limit=limit)


def save_schema(schema: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
