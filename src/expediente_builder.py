from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

from clean_data import normalize_key
from config import REVIEW_RECOMMENDATION

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


EXPECTED_DOCUMENTS = [
    "estudios previos",
    "CDP",
    "RP",
    "pliego/invitación",
    "ofertas",
    "acta de evaluación",
    "contrato firmado",
    "actas de modificación",
    "actas de pago",
    "acta de cancelación, si aplica",
]


def _similarity(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if fuzz:
        return int(fuzz.token_set_ratio(left, right))
    left_words = set(left.split())
    right_words = set(right.split())
    if not left_words or not right_words:
        return 0
    return int(100 * len(left_words & right_words) / len(left_words | right_words))


def _close_dates(left: object, right: object, days: int = 90) -> bool:
    if pd.isna(left) or pd.isna(right):
        return False
    return abs((right - left).days) <= days


def _close_values(left: float, right: float) -> bool:
    if left <= 0 or right <= 0:
        return False
    return abs(left - right) / max(left, right) <= 0.05


def _stable_id(values: list[str], prefix: str = "EXP") -> str:
    raw = "|".join(sorted(v for v in values if v))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{prefix}-{int(digest[:10], 16) % 100_000_000:08d}"


class UnionFind:
    def __init__(self, indexes: list[int]) -> None:
        self.parent = {idx: idx for idx in indexes}

    def find(self, item: int) -> int:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def _matching_reasons(left: pd.Series, right: pd.Series) -> list[str]:
    reasons: list[str] = []
    exact_keys = [
        "id_del_proceso",
        "proceso_de_compra",
        "referencia_del_proceso",
        "referencia_del_contrato",
        "documentos_o_url",
        "notice_uid",
    ]
    for key in exact_keys:
        left_value = normalize_key(left.get(key, ""))
        right_value = normalize_key(right.get(key, ""))
        if left_value and right_value and left_value == right_value:
            reasons.append(f"coincidencia por {key}")

    same_entity = bool(left.get("entidad_norm")) and left.get("entidad_norm") == right.get("entidad_norm")
    same_provider = bool(left.get("proveedor_norm")) and left.get("proveedor_norm") == right.get("proveedor_norm")
    object_similarity = _similarity(str(left.get("objeto_norm", "")), str(right.get("objeto_norm", "")))
    close_values = _close_values(float(left.get("valor_analisis", 0) or 0), float(right.get("valor_analisis", 0) or 0))
    close_dates = _close_dates(left.get("fecha"), right.get("fecha"))

    if same_entity and object_similarity >= 88 and (same_provider or close_values or close_dates):
        reasons.append(f"misma entidad y objeto similar ({object_similarity}%)")
    if same_provider and object_similarity >= 85 and close_dates:
        reasons.append(f"mismo proveedor, objeto similar ({object_similarity}%) y fechas cercanas")
    if same_entity and close_values and close_dates and object_similarity >= 80:
        reasons.append("misma entidad, valor similar y fechas cercanas")
    return reasons


def assign_expediente_ids(scored: pd.DataFrame) -> pd.DataFrame:
    df = scored.copy()
    if df.empty:
        df["expediente_id"] = []
        df["criterios_relacion"] = []
        return df

    uf = UnionFind(list(df.index))
    criteria: dict[int, set[str]] = defaultdict(set)
    for left_idx, right_idx in combinations(df.index, 2):
        left = df.loc[left_idx]
        right = df.loc[right_idx]
        reasons = _matching_reasons(left, right)
        if reasons:
            uf.union(left_idx, right_idx)
            criteria[left_idx].update(reasons)
            criteria[right_idx].update(reasons)

    groups: dict[int, list[int]] = defaultdict(list)
    for idx in df.index:
        groups[uf.find(idx)].append(idx)

    expediente_ids: dict[int, str] = {}
    for indexes in groups.values():
        values = []
        for idx in indexes:
            row = df.loc[idx]
            values.extend([
                str(row.get("notice_uid", "")),
                str(row.get("proceso_de_compra", "")),
                str(row.get("id_del_proceso", "")),
                str(row.get("id_contrato", "")),
                str(row.get("referencia_del_proceso", "")),
                str(row.get("referencia_del_contrato", "")),
                str(row.get("entidad_norm", "")),
                str(row.get("objeto_norm", ""))[:120],
            ])
        expediente_id = _stable_id(values)
        for idx in indexes:
            expediente_ids[idx] = expediente_id

    df["expediente_id"] = df.index.map(expediente_ids)
    df["criterios_relacion"] = df.index.map(lambda idx: "; ".join(sorted(criteria.get(idx, []))))
    return df


def _risk_rank(level: str) -> int:
    return {"Bajo": 0, "Medio": 1, "Alto": 2, "Crítico": 3}.get(str(level), -1)


def _join_unique(values: pd.Series, limit: int = 12) -> str:
    items = []
    for value in values.dropna().astype(str):
        value = value.strip()
        if value and value not in items:
            items.append(value)
    return "; ".join(items[:limit])


def _missing_documents(group: pd.DataFrame) -> str:
    docs = EXPECTED_DOCUMENTS.copy()
    if not group["estado_norm"].str.contains("CANCEL", na=False).any():
        docs = [doc for doc in docs if "cancelación" not in doc]
    if (group["fuente"] == "contratos").any():
        docs = [doc for doc in docs if doc != "contrato firmado"]
    return "; ".join(docs)


def build_expedientes(scored: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    related = assign_expediente_ids(scored)
    expedientes = []
    for expediente_id, group in related.groupby("expediente_id", dropna=False):
        risk_level = sorted(group["nivel_riesgo"].dropna().unique(), key=_risk_rank, reverse=True)
        risk = risk_level[0] if risk_level else "Bajo"
        fechas = pd.to_datetime(group["fecha"], errors="coerce").dropna()
        expedientes.append(
            {
                "expediente_id": expediente_id,
                "entidad": _join_unique(group["entidad"], 3),
                "proveedor": _join_unique(group["proveedor"], 5),
                "objeto_consolidado": _join_unique(group["objeto"], 3),
                "valor_estimado_total": group["valor_estimado"].sum(),
                "valor_adjudicado_total": group["valor_adjudicado"].sum(),
                "valor_contratado_total": group.loc[group["fuente"] == "contratos", "valor_analisis"].sum(),
                "valor_analisis_total": group["valor_analisis"].sum(),
                "fechas_relevantes": f"{fechas.min().date()} a {fechas.max().date()}" if not fechas.empty else "",
                "registros_relacionados": _join_unique(group["id_registro"], 30),
                "enlaces_secop": _join_unique(group["documentos_o_url"], 20),
                "razones_alerta": _join_unique(group["razones_alerta"], 8),
                "nivel_riesgo": risk,
                "score_max": group["score_riesgo"].max(),
                "documentos_faltantes": _missing_documents(group),
                "recomendacion": REVIEW_RECOMMENDATION,
                "cantidad_registros": len(group),
                "contratos_relacionados": int((group["fuente"] == "contratos").sum()),
                "procesos_relacionados": int((group["fuente"] == "procesos").sum()),
            }
        )
    expedientes_df = pd.DataFrame(expedientes).sort_values(["score_max", "valor_analisis_total"], ascending=False)
    return expedientes_df, {
        "related": related,
        "procesos": related[related["fuente"] == "procesos"].copy(),
        "contratos": related[related["fuente"] == "contratos"].copy(),
    }


def _safe_sheet(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str) -> None:
    export = df.copy()
    for column in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[column]):
            export[column] = export[column].dt.strftime("%Y-%m-%d")
    export.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def generate_expedientes_excel(expedientes: pd.DataFrame, tables: dict[str, pd.DataFrame], output_path: Path) -> None:
    related = tables["related"]
    evidence_cols = [
        "expediente_id", "caso_id", "id_registro", "fuente", "entidad", "proveedor",
        "valor_analisis", "fecha", "nivel_riesgo", "tipo_alerta", "evidencia_minima",
        "criterios_relacion", "documentos_o_url",
    ]
    links = related[["expediente_id", "id_registro", "fuente", "notice_uid", "documentos_o_url"]].copy()
    manual = expedientes[
        (expedientes["score_max"] >= 61)
        | (expedientes["contratos_relacionados"].eq(0))
        | (expedientes["enlaces_secop"].eq(""))
    ].copy()
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _safe_sheet(expedientes, writer, "Expedientes Priorizados")
        _safe_sheet(tables["procesos"], writer, "Procesos Relacionados")
        _safe_sheet(tables["contratos"], writer, "Contratos Relacionados")
        _safe_sheet(related[[c for c in evidence_cols if c in related.columns]], writer, "Evidencia SECOP")
        _safe_sheet(links, writer, "Links Oficiales")
        _safe_sheet(manual, writer, "Casos Para Revisión Manual")


def _slug(value: str) -> str:
    text = normalize_key(value)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")[:50] or "SIN_RIESGO"


def _md_escape(text: object) -> str:
    return ("" if pd.isna(text) else str(text)).replace("|", "\\|")


def generate_expediente_markdowns(expedientes: pd.DataFrame, related: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("EXPEDIENTE_*.md"):
        old_file.unlink()
    for _, expediente in expedientes.iterrows():
        expediente_id = expediente["expediente_id"]
        group = related[related["expediente_id"] == expediente_id].copy()
        rows = []
        for _, row in group.iterrows():
            rows.append(
                f"| {_md_escape(row.get('id_registro'))} | {_md_escape(row.get('fuente'))} | "
                f"{_md_escape(row.get('valor_analisis'))} | {_md_escape(row.get('fecha'))} | "
                f"{_md_escape(row.get('nivel_riesgo'))} | {_md_escape(row.get('documentos_o_url'))} |"
            )
        content = f"""# Expediente preliminar {expediente_id}

Este expediente preliminar reúne indicios documentales de riesgo contractual. No afirma corrupción confirmada ni responsabilidad penal, fiscal o disciplinaria. Es un caso con evidencia suficiente para revisión o traslado y requiere revisión de autoridad competente.

## Resumen

- Entidad: {expediente['entidad']}
- Proveedor: {expediente['proveedor']}
- Nivel de riesgo: {expediente['nivel_riesgo']}
- Valor estimado total: ${expediente['valor_estimado_total']:,.0f}
- Valor adjudicado total: ${expediente['valor_adjudicado_total']:,.0f}
- Valor contratado total: ${expediente['valor_contratado_total']:,.0f}
- Fechas relevantes: {expediente['fechas_relevantes']}

## Objeto Consolidado

{expediente['objeto_consolidado']}

## Registros Relacionados

| id_registro | fuente | valor_analisis | fecha | nivel_riesgo | enlace SECOP |
|---|---|---:|---|---|---|
{chr(10).join(rows)}

## Razones de Alerta

{expediente['razones_alerta']}

## Documentos Faltantes Esperados

{expediente['documentos_faltantes']}

## Enlaces SECOP

{expediente['enlaces_secop']}

## Recomendación

{expediente['recomendacion']}
"""
        filename = f"EXPEDIENTE_{expediente_id}_{_slug(expediente['nivel_riesgo'])}.md"
        (output_dir / filename).write_text(content, encoding="utf-8")


def generate_expediente_outputs(scored: pd.DataFrame, excel_path: Path, markdown_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    expedientes, tables = build_expedientes(scored)
    generate_expedientes_excel(expedientes, tables, excel_path)
    generate_expediente_markdowns(expedientes, tables["related"], markdown_dir)
    return expedientes, tables["related"]
