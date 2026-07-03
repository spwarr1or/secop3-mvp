from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


MISSING_VALUES = {"", "NO DEFINIDO", "NO DEFINIDA", "NO APLICA", "N/A", "NA", "NONE", "NULL", "NAN"}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, dict):
        value = value.get("url", "")
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    if text.upper() in MISSING_VALUES:
        return ""
    return text


def normalize_key(value: Any) -> str:
    text = strip_accents(normalize_text(value)).upper()
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def first_available(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for column in candidates:
        if column in df.columns:
            return df[column]
    return pd.Series([""] * len(df), index=df.index)


def extract_url(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_text(value.get("url", ""))
    return normalize_text(value)


def extract_notice_uid(url: Any) -> str:
    text = extract_url(url)
    match = re.search(r"(?:noticeUID|noticeuid)=([^&]+)", text, flags=re.IGNORECASE)
    return normalize_text(match.group(1)) if match else ""


def clean_money(value: Any) -> float:
    text = normalize_text(value)
    if not text:
        return 0.0
    text = text.replace("$", "").replace("COP", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text) if text not in {"", ".", "-"} else 0.0
    except ValueError:
        return 0.0


def clean_int(value: Any) -> int:
    return int(clean_money(value))


def clean_date(value: Any) -> pd.Timestamp | pd.NaT:
    text = normalize_text(value)
    if not text:
        return pd.NaT
    return pd.to_datetime(text, errors="coerce", dayfirst=False)


def _first_non_empty_key(row: pd.Series, candidates: list[str]) -> str:
    for column in candidates:
        value = normalize_text(row.get(column, ""))
        if value:
            return f"{column}:{normalize_key(value)}"
    return ""


def clean_dataset(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    cleaned = df.copy()
    if cleaned.empty:
        return _empty_clean_frame(fuente)

    if fuente == "contratos":
        id_candidates = ["id_contrato", "referencia_del_contrato", "proceso_de_compra"]
        start_candidates = ["fecha_de_inicio_del_contrato", "fecha_de_inicio"]
        sign_candidates = ["fecha_de_firma", "fecha_de_publicacion_del"]
        provider_candidates = ["proveedor_adjudicado", "nombre_del_proveedor", "nombre_del_proveedor_adjudicado"]
        entity_candidates = ["nombre_entidad", "entidad"]
        object_candidates = ["objeto_del_contrato", "descripcion_del_proceso", "descripci_n_del_procedimiento"]
        city_candidates = ["ciudad", "ciudad_entidad"]
        department_candidates = ["departamento", "departamento_entidad"]
        status_candidates = ["estado_contrato", "estado_del_procedimiento", "estado_resumen"]
    else:
        id_candidates = ["id_del_proceso", "referencia_del_proceso", "id_del_portafolio"]
        start_candidates = ["fecha_de_publicacion_del", "fecha_de_publicacion_fase_3"]
        sign_candidates = ["fecha_de_ultima_publicaci", "fecha_de_publicacion_del"]
        provider_candidates = ["nombre_del_proveedor", "nombre_del_proveedor_adjudicado", "nit_del_proveedor_adjudicado"]
        entity_candidates = ["entidad", "nombre_entidad"]
        object_candidates = ["descripci_n_del_procedimiento", "nombre_del_procedimiento", "objeto_del_contrato"]
        city_candidates = ["ciudad_entidad", "ciudad", "ciudad_de_la_unidad_de"]
        department_candidates = ["departamento_entidad", "departamento"]
        status_candidates = ["estado_del_procedimiento", "estado_resumen", "fase"]

    cleaned["id_registro"] = first_available(cleaned, id_candidates).map(normalize_text)
    missing_id = cleaned["id_registro"].eq("")
    cleaned.loc[missing_id, "id_registro"] = [f"{fuente}-{i}" for i in cleaned.index[missing_id]]

    cleaned["valor_estimado"] = 0.0
    cleaned["valor_adjudicado"] = 0.0
    if fuente == "contratos":
        cleaned["valor_adjudicado"] = first_available(cleaned, ["valor_del_contrato"]).map(clean_money)
        cleaned["valor_estimado"] = cleaned["valor_adjudicado"]
    else:
        cleaned["valor_estimado"] = first_available(cleaned, ["precio_base"]).map(clean_money)
        cleaned["valor_adjudicado"] = first_available(cleaned, ["valor_total_adjudicacion"]).map(clean_money)
    cleaned["valor_analisis"] = cleaned["valor_adjudicado"].where(cleaned["valor_adjudicado"] > 0, cleaned["valor_estimado"])
    cleaned["valor_num"] = cleaned["valor_analisis"]

    cleaned["fecha_inicio_norm"] = first_available(cleaned, start_candidates).map(clean_date)
    cleaned["fecha_firma_norm"] = first_available(cleaned, sign_candidates).map(clean_date)
    cleaned["fecha"] = cleaned["fecha_firma_norm"].fillna(cleaned["fecha_inicio_norm"])
    cleaned["proveedor"] = first_available(cleaned, provider_candidates).map(normalize_text)
    cleaned["entidad"] = first_available(cleaned, entity_candidates).map(normalize_text)
    cleaned["objeto"] = first_available(cleaned, object_candidates).map(normalize_text)
    cleaned["modalidad"] = first_available(cleaned, ["modalidad_de_contratacion", "modalidad"]).map(normalize_text)
    cleaned["municipio"] = first_available(cleaned, city_candidates).map(normalize_text)
    cleaned["departamento"] = first_available(cleaned, department_candidates).map(normalize_text)
    cleaned["estado"] = first_available(cleaned, status_candidates).map(normalize_text)
    cleaned["adjudicado"] = first_available(cleaned, ["adjudicado"]).map(normalize_text)

    cleaned["proveedores_invitados_num"] = first_available(cleaned, ["proveedores_invitados"]).map(clean_int)
    cleaned["respuestas_num"] = first_available(cleaned, ["respuestas_al_procedimiento", "conteo_de_respuestas_a_ofertas"]).map(clean_int)
    cleaned["proveedores_unicos_num"] = first_available(cleaned, ["proveedores_unicos_con"]).map(clean_int)

    cleaned["proveedor_norm"] = cleaned["proveedor"].map(normalize_key)
    cleaned["entidad_norm"] = cleaned["entidad"].map(normalize_key)
    cleaned["objeto_norm"] = cleaned["objeto"].map(normalize_key)
    cleaned["modalidad_norm"] = cleaned["modalidad"].map(normalize_key)
    cleaned["municipio_norm"] = cleaned["municipio"].map(normalize_key)
    cleaned["departamento_norm"] = cleaned["departamento"].map(normalize_key)
    cleaned["estado_norm"] = cleaned["estado"].map(normalize_key)
    cleaned["fuente"] = fuente

    cleaned["documentos_o_url"] = first_available(cleaned, ["urlproceso", "url_proceso", "url"]).map(extract_url)
    cleaned["notice_uid"] = cleaned["documentos_o_url"].map(extract_notice_uid)
    for column in [
        "proceso_de_compra", "id_del_proceso", "id_contrato",
        "referencia_del_proceso", "referencia_del_contrato",
    ]:
        cleaned[column] = cleaned[column].map(normalize_text) if column in cleaned.columns else ""
        cleaned[f"{column}_norm"] = cleaned[column].map(normalize_key)

    cleaned["llave_deduplicacion"] = cleaned.apply(
        lambda row: _first_non_empty_key(
            row,
            [
                "notice_uid", "proceso_de_compra", "id_del_proceso", "id_contrato",
                "referencia_del_proceso", "referencia_del_contrato",
            ],
        )
        or f"{fuente}:{normalize_key(row.get('id_registro', ''))}",
        axis=1,
    )
    return cleaned


def _empty_clean_frame(fuente: str) -> pd.DataFrame:
    columns = [
        "id_registro", "valor_estimado", "valor_adjudicado", "valor_analisis", "valor_num",
        "fecha_inicio_norm", "fecha_firma_norm", "fecha", "proveedor", "entidad", "objeto",
        "modalidad", "municipio", "departamento", "estado", "adjudicado", "proveedor_norm",
        "entidad_norm", "objeto_norm", "modalidad_norm", "municipio_norm", "departamento_norm",
        "estado_norm", "fuente", "documentos_o_url", "notice_uid", "llave_deduplicacion",
        "proveedores_invitados_num", "respuestas_num", "proveedores_unicos_num",
    ]
    frame = pd.DataFrame(columns=columns)
    frame["fuente"] = fuente
    return frame
