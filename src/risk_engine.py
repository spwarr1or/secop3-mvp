from __future__ import annotations

from collections import defaultdict
import hashlib
from itertools import combinations

import pandas as pd

from clean_data import normalize_key
from config import REVIEW_RECOMMENDATION

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


GENERIC_OBJECT_TERMS = [
    "PRESTACION DE SERVICIOS",
    "APOYO A LA GESTION",
    "SERVICIOS PROFESIONALES",
    "SUMINISTRO",
    "MANTENIMIENTO",
    "CONSULTORIA",
    "ASESORIA",
]


def _similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if fuzz:
        return int(fuzz.token_set_ratio(a, b))
    a_words = set(a.split())
    b_words = set(b.split())
    if not a_words or not b_words:
        return 0
    return int(100 * len(a_words & b_words) / len(a_words | b_words))


def _days_between(left: pd.Timestamp, right: pd.Timestamp) -> int | None:
    if pd.isna(left) or pd.isna(right):
        return None
    return abs((right - left).days)


def _same_procurement(left: pd.Series, right: pd.Series) -> bool:
    keys = [
        "notice_uid", "proceso_de_compra", "id_del_proceso", "id_contrato",
        "referencia_del_proceso", "referencia_del_contrato", "llave_deduplicacion",
    ]
    for key in keys:
        left_value = normalize_key(left.get(key, ""))
        right_value = normalize_key(right.get(key, ""))
        if left_value and right_value and left_value == right_value:
            return True
    return False


def _append_related(
    flags: dict[int, set[str]],
    evidence: dict[int, list[str]],
    left_idx: int,
    right_idx: int,
    label: str,
    text: str,
) -> None:
    flags[left_idx].add(label)
    flags[right_idx].add(label)
    evidence[left_idx].append(text)
    evidence[right_idx].append(text)


def detect_related_cases(df: pd.DataFrame) -> tuple[dict[int, set[str]], dict[int, list[str]]]:
    flags: dict[int, set[str]] = defaultdict(set)
    evidence: dict[int, list[str]] = defaultdict(list)
    if df.empty:
        return flags, evidence

    working = df.drop_duplicates("llave_deduplicacion", keep="first").copy()
    working = working[working["fecha"].notna() & working["objeto_norm"].ne("")]

    for _, group in working.groupby("entidad_norm"):
        records = list(group.itertuples(index=True))
        for left, right in combinations(records, 2):
            left_row = df.loc[left.Index]
            right_row = df.loc[right.Index]
            if _same_procurement(left_row, right_row):
                continue
            days = _days_between(left.fecha, right.fecha)
            if days is None or days > 60:
                continue
            similarity = _similarity(left.objeto_norm, right.objeto_norm)
            if similarity < 82:
                continue

            pair_text = (
                f"{left.id_registro} y {right.id_registro}: objeto similar "
                f"({similarity}%) en la misma entidad con {days} días de diferencia"
            )
            _append_related(flags, evidence, left.Index, right.Index, "procesos_repetidos", pair_text)

            if left.proveedor_norm and right.proveedor_norm and left.proveedor_norm == right.proveedor_norm:
                _append_related(flags, evidence, left.Index, right.Index, "posible_fraccionamiento", pair_text)

            if "REGIMEN ESPECIAL" in left.modalidad_norm and "REGIMEN ESPECIAL" in right.modalidad_norm:
                _append_related(flags, evidence, left.Index, right.Index, "regimen_especial_repetido", pair_text)

    status_terms = ("CANCEL", "REPUBLIC")
    for _, group in working.groupby("entidad_norm"):
        records = list(group.itertuples(index=True))
        for left, right in combinations(records, 2):
            left_status = left.estado_norm
            right_status = right.estado_norm
            has_cancel_or_republish = any(term in left_status for term in status_terms) or any(term in right_status for term in status_terms)
            if not has_cancel_or_republish or _same_procurement(df.loc[left.Index], df.loc[right.Index]):
                continue
            similarity = _similarity(left.objeto_norm, right.objeto_norm)
            if similarity >= 82:
                text = f"{left.id_registro} y {right.id_registro}: posible cancelación/republicación con objeto similar ({similarity}%)"
                _append_related(flags, evidence, left.Index, right.Index, "cancelado_republicado", text)

    return flags, evidence


def classify_risk(score: int) -> str:
    if score <= 30:
        return "Bajo"
    if score <= 60:
        return "Medio"
    if score <= 80:
        return "Alto"
    return "Crítico"


def _case_id(row: pd.Series) -> str:
    key = normalize_key(row.get("llave_deduplicacion", "")) or normalize_key(row.get("id_registro", ""))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"CASO-{int(digest[:8], 16) % 10_000_000:07d}"


def score_risk(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    if scored.empty:
        for column in [
            "score_riesgo", "nivel_riesgo", "razones_alerta", "recomendacion_revision",
            "posible_fraccionamiento", "procesos_repetidos", "baja_competencia",
            "cancelado_republicado", "caso_id", "grupo_relacionado", "tipo_alerta",
            "evidencia_minima", "accion_recomendada",
        ]:
            scored[column] = []
        return scored

    scored["valor_analisis"] = pd.to_numeric(scored.get("valor_analisis", 0), errors="coerce").fillna(0)
    scored["valor_num"] = scored["valor_analisis"]
    q90 = scored.loc[scored["valor_analisis"] > 0, "valor_analisis"].quantile(0.90)
    q95 = scored.loc[scored["valor_analisis"] > 0, "valor_analisis"].quantile(0.95)
    related_flags, related_evidence = detect_related_cases(scored)

    scores: list[int] = []
    reasons: list[str] = []
    alert_types: list[str] = []
    evidence_min: list[str] = []
    groups: list[str] = []
    cases: list[str] = []

    for idx, row in scored.iterrows():
        score = 0
        row_reasons: list[str] = []
        row_alerts: list[str] = []

        if "DIRECTA" in row.get("modalidad_norm", ""):
            score += 25
            row_reasons.append("Contratación directa")
            row_alerts.append("contratacion_directa")

        value = float(row.get("valor_analisis", 0) or 0)
        if value > 0 and pd.notna(q95) and value >= q95:
            score += 30
            row_reasons.append("Valor en top 5% por valor_analisis")
            row_alerts.append("top_valor")
        elif value > 0 and pd.notna(q90) and value >= q90:
            score += 20
            row_reasons.append("Valor en top 10% por valor_analisis")
            row_alerts.append("top_valor")

        if row.get("fuente") == "procesos" and value > 100_000_000:
            score += 20
            row_reasons.append("Proceso con valor_analisis mayor a 100M COP")
            row_alerts.append("valor_mayor_100m")

        flags = related_flags.get(idx, set())
        if "procesos_repetidos" in flags:
            score += 25
            row_reasons.append("Procesos repetidos con objeto similar, misma entidad y fechas cercanas")
            row_alerts.append("procesos_repetidos")
        if "posible_fraccionamiento" in flags:
            score += 25
            row_reasons.append("Posible fraccionamiento sin comparar proceso contra su propio contrato asociado")
            row_alerts.append("posible_fraccionamiento")
        if "regimen_especial_repetido" in flags:
            score += 15
            row_reasons.append("Régimen especial repetido con objeto similar")
            row_alerts.append("regimen_especial_repetido")
        if "cancelado_republicado" in flags:
            score += 20
            row_reasons.append("Cancelado/republicado con objeto similar")
            row_alerts.append("cancelado_republicado")

        invited = int(row.get("proveedores_invitados_num", 0) or 0)
        responses = int(row.get("respuestas_num", 0) or 0)
        unique_suppliers = int(row.get("proveedores_unicos_num", 0) or 0)
        if row.get("fuente") == "procesos" and invited == 0 and responses == 0:
            score += 10
            row_reasons.append("Baja competencia: proveedores invitados = 0 y respuestas = 0")
            row_alerts.append("baja_competencia")
        if row.get("fuente") == "procesos" and (unique_suppliers == 1 or normalize_key(row.get("adjudicado", "")) == "SI"):
            score += 15
            row_reasons.append("Baja competencia: proveedor adjudicado único, si aplica")
            row_alerts.append("proveedor_unico")

        object_norm = row.get("objeto_norm", "")
        if any(term in object_norm for term in GENERIC_OBJECT_TERMS):
            score += 10
            row_reasons.append("Objeto contractual genérico o recurrente")
            row_alerts.append("objeto_generico")

        missing = []
        if not row.get("proveedor_norm", "") and row.get("fuente") == "contratos":
            missing.append("proveedor")
        if value <= 0:
            missing.append("valor")
        if not row.get("modalidad_norm", ""):
            missing.append("modalidad")
        if not object_norm:
            missing.append("objeto")
        if pd.isna(row.get("fecha")):
            missing.append("fecha")
        if missing:
            score += 10
            row_reasons.append(f"Faltan datos críticos: {', '.join(missing)}")
            row_alerts.append("datos_incompletos")

        evidence = related_evidence.get(idx, [])
        minimal = "; ".join(evidence[:3])
        if not minimal:
            minimal = "; ".join(row_reasons[:3]) if row_reasons else "Sin indicios documentales automáticos relevantes"

        case_id = _case_id(row)
        cases.append(case_id)
        groups.append(row.get("llave_deduplicacion", "") or case_id)
        scores.append(min(score, 100))
        reasons.append(" | ".join(row_reasons) if row_reasons else "Sin alertas automáticas relevantes")
        alert_types.append(", ".join(dict.fromkeys(row_alerts)) if row_alerts else "sin_alerta")
        evidence_min.append(minimal)

    scored["score_riesgo"] = scores
    scored["nivel_riesgo"] = scored["score_riesgo"].map(classify_risk)
    scored["razones_alerta"] = reasons
    scored["tipo_alerta"] = alert_types
    scored["evidencia_minima"] = evidence_min
    scored["caso_id"] = cases
    scored["grupo_relacionado"] = groups
    scored["posible_fraccionamiento"] = scored["tipo_alerta"].str.contains("posible_fraccionamiento", na=False)
    scored["procesos_repetidos"] = scored["tipo_alerta"].str.contains("procesos_repetidos", na=False)
    scored["baja_competencia"] = scored["tipo_alerta"].str.contains("baja_competencia|proveedor_unico", na=False)
    scored["cancelado_republicado"] = scored["tipo_alerta"].str.contains("cancelado_republicado", na=False)
    scored["accion_recomendada"] = REVIEW_RECOMMENDATION
    scored["recomendacion_revision"] = REVIEW_RECOMMENDATION
    return scored


def evidence_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "caso_id", "grupo_relacionado", "id_registro", "fuente", "entidad", "proveedor",
        "valor_estimado", "valor_adjudicado", "valor_analisis", "modalidad", "estado",
        "fecha", "objeto", "score_riesgo", "nivel_riesgo", "tipo_alerta", "razones_alerta",
        "evidencia_minima", "documentos_o_url", "accion_recomendada",
    ]
    present = [column for column in columns if column in df.columns]
    return df[present]
