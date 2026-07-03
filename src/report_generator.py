from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import LEGAL_NOTE
from risk_engine import evidence_columns


def _safe_sheet(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str) -> None:
    export = df.copy()
    for column in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[column]):
            export[column] = export[column].dt.strftime("%Y-%m-%d")
    export.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def _dictionary(scored: pd.DataFrame) -> pd.DataFrame:
    descriptions = {
        "valor_estimado": "Precio base del proceso o valor del contrato cuando aplica.",
        "valor_adjudicado": "Valor adjudicado. En contratos corresponde a valor_del_contrato; en procesos a valor_total_adjudicacion.",
        "valor_analisis": "Valor usado para score: valor_adjudicado si es mayor a 0; si no, valor_estimado.",
        "caso_id": "Identificador estable del caso de revisión generado por el MVP.",
        "grupo_relacionado": "Llave usada para agrupar registros relacionados o deduplicados.",
        "tipo_alerta": "Categorías de alerta activadas por reglas automáticas.",
        "evidencia_minima": "Resumen mínimo de indicios documentales detectados.",
        "accion_recomendada": "Acción sugerida sin afirmar corrupción confirmada.",
    }
    return pd.DataFrame(
        [{"campo": column, "descripcion": descriptions.get(column, "Campo detectado o calculado por el MVP.")}
         for column in scored.columns]
    )


def generate_excel(
    contratos: pd.DataFrame,
    procesos: pd.DataFrame,
    all_scored: pd.DataFrame,
    output_path: Path,
) -> None:
    top_risk = evidence_columns(all_scored.sort_values("score_riesgo", ascending=False).head(50))
    top_value = evidence_columns(all_scored.sort_values("valor_analisis", ascending=False).head(50))
    fraction = evidence_columns(all_scored[all_scored["posible_fraccionamiento"]].sort_values("score_riesgo", ascending=False))
    repeated = evidence_columns(all_scored[all_scored["procesos_repetidos"]].sort_values("score_riesgo", ascending=False))
    direct = evidence_columns(all_scored[all_scored["modalidad_norm"].str.contains("DIRECTA", na=False)])
    low_competition = evidence_columns(all_scored[all_scored["baja_competencia"]].sort_values("score_riesgo", ascending=False))
    summary = pd.DataFrame(
        [
            {"indicador": "Registros analizados", "valor": len(all_scored)},
            {"indicador": "Valor total analizado", "valor": all_scored["valor_analisis"].sum()},
            {"indicador": "Proveedores únicos", "valor": all_scored["proveedor_norm"].replace("", pd.NA).nunique()},
            {"indicador": "Alertas altas", "valor": int((all_scored["nivel_riesgo"] == "Alto").sum())},
            {"indicador": "Alertas críticas", "valor": int((all_scored["nivel_riesgo"] == "Crítico").sum())},
            {"indicador": "Casos posible fraccionamiento", "valor": int(all_scored["posible_fraccionamiento"].sum())},
            {"indicador": "Casos baja competencia", "valor": int(all_scored["baja_competencia"].sum())},
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _safe_sheet(summary, writer, "Resumen")
        _safe_sheet(top_risk, writer, "Top Riesgo")
        _safe_sheet(top_value, writer, "Top Valor")
        _safe_sheet(fraction, writer, "Posible Fraccionamiento")
        _safe_sheet(repeated, writer, "Procesos Repetidos")
        _safe_sheet(direct, writer, "Contratación Directa")
        _safe_sheet(low_competition, writer, "Baja Competencia")
        _safe_sheet(contratos, writer, "Datos Contratos")
        _safe_sheet(procesos, writer, "Datos Procesos")
        _safe_sheet(_dictionary(all_scored), writer, "Diccionario de Campos")


def _escape_markdown(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "Sin registros para esta sección.\n"
    present = [column for column in columns if column in df.columns]
    export = df[present].head(max_rows).copy()
    for column in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[column]):
            export[column] = export[column].dt.strftime("%Y-%m-%d")
        export[column] = export[column].map(_escape_markdown)
    return export.to_markdown(index=False) + "\n"


def generate_markdown(all_scored: pd.DataFrame, output_path: Path, municipio: str, departamento: str) -> None:
    top20_risk = all_scored.sort_values("score_riesgo", ascending=False).head(20)
    top10_value = all_scored.sort_values("valor_analisis", ascending=False).head(10)
    repeated = all_scored[all_scored["procesos_repetidos"]].sort_values("score_riesgo", ascending=False)
    canceled = all_scored[all_scored["cancelado_republicado"]].sort_values("score_riesgo", ascending=False)
    fraction = all_scored[all_scored["posible_fraccionamiento"]].sort_values("score_riesgo", ascending=False)
    high = int((all_scored["nivel_riesgo"] == "Alto").sum())
    critical = int((all_scored["nivel_riesgo"] == "Crítico").sum())

    common_columns = [
        "caso_id", "id_registro", "fuente", "entidad", "proveedor", "valor_analisis",
        "modalidad", "fecha", "score_riesgo", "nivel_riesgo", "tipo_alerta",
        "evidencia_minima", "documentos_o_url",
    ]
    content = f"""# Radiografía Contractual — {municipio}, {departamento}

## Resumen Ejecutivo

Este MVP analiza datos públicos de SECOP II para identificar indicios documentales y alertas de riesgo contractual. Se analizaron {len(all_scored):,} registros, con {high:,} alertas altas y {critical:,} alertas críticas. Cada hallazgo debe entenderse como caso con evidencia suficiente para revisión o traslado a autoridad competente, no como conclusión de corrupción.

## Datos Analizados

- Fuentes: SECOP II Contratos Electrónicos y SECOP II Procesos de Contratación.
- Valor total analizado con `valor_analisis`: ${all_scored['valor_analisis'].sum():,.0f}
- Proveedores únicos: {all_scored['proveedor_norm'].replace('', pd.NA).nunique():,}

## Principales Alertas

Las señales revisadas incluyen contratación directa, top de valor por `valor_analisis`, procesos mayores a 100M COP, procesos repetidos con objeto similar, posible fraccionamiento sin comparar proceso contra su contrato asociado, régimen especial repetido, baja competencia y cancelación/republicación con objeto similar.

## Top 20 Registros de Riesgo

{_markdown_table(top20_risk, common_columns, 20)}

## Top 10 Registros por Valor

{_markdown_table(top10_value, common_columns, 10)}

## Procesos Repetidos con Objeto Similar

{_markdown_table(repeated, common_columns, 20)}

## Posibles Casos de Fraccionamiento

{_markdown_table(fraction, common_columns, 20)}

## Procesos Cancelados o Republicados

{_markdown_table(canceled, common_columns, 20)}

## Limitaciones del Análisis

El análisis depende de la calidad, completitud y oportunidad de los datos publicados. Las reglas son heurísticas iniciales y no reemplazan revisión jurídica, fiscal, disciplinaria ni auditoría documental. Algunas columnas pueden venir vacías, cambiar de nombre o contener valores no estandarizados.

## Recomendaciones

- Revisar documentalmente los registros con nivel Alto o Crítico.
- Priorizar casos con evidencia mínima de objeto similar, fechas cercanas, baja competencia o valores altos.
- Contrastar estudios previos, CDP/RP, pliegos, ofertas, adjudicación, supervisión y soportes de ejecución.
- Usar los hallazgos como insumo de control interno, veeduría o traslado a autoridad competente cuando corresponda.

## Nota Jurídica

“{LEGAL_NOTE}”
"""
    output_path.write_text(content, encoding="utf-8")
