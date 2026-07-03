from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_DEPARTMENT, DEFAULT_LIMIT, DEFAULT_MUNICIPALITY, OUTPUTS_DIR
from territories import cities_for_department, departments


st.set_page_config(page_title="SECOP 3.0", layout="wide")
st.title("SECOP 3.0")


def current_run_path() -> Path:
    return OUTPUTS_DIR / "current_run.json"


@st.cache_data(show_spinner=False)
def read_current_run() -> dict:
    path = current_run_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_analysis(departamento: str, municipio: str, limit: int) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        "src/main.py",
        "--departamento",
        departamento,
        "--municipio",
        municipio,
        "--limit",
        str(limit),
    ]
    completed = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=900)
    read_current_run.clear()
    load_data.clear()
    load_expedientes.clear()
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    return completed.returncode == 0, output.strip()


@st.cache_data
def load_data(run: dict) -> pd.DataFrame:
    frames = []
    for key in ("contratos_limpios", "procesos_limpios"):
        path = Path(run.get(key, ""))
        if path.exists():
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data
def load_expedientes(run: dict) -> pd.DataFrame:
    path = Path(run.get("expedientes_excel", ""))
    if not path.exists():
        return pd.DataFrame()
    return pd.read_excel(path, sheet_name="Expedientes Priorizados")


def linkify(url: object) -> str:
    text = "" if pd.isna(url) else str(url)
    return f'<a href="{text}" target="_blank">Abrir SECOP</a>' if text.startswith("http") else ""


with st.sidebar:
    st.header("Territorio")
    department_options = departments()
    default_department_index = department_options.index(DEFAULT_DEPARTMENT) if DEFAULT_DEPARTMENT in department_options else 0
    departamento_input = st.selectbox("Departamento", department_options, index=default_department_index)
    city_options = cities_for_department(departamento_input)
    default_city_index = city_options.index(DEFAULT_MUNICIPALITY) if DEFAULT_MUNICIPALITY in city_options else 0
    municipio_input = st.selectbox("Ciudad / municipio", city_options, index=default_city_index)
    limit_input = st.number_input("Límite por dataset", min_value=1, max_value=50000, value=min(DEFAULT_LIMIT, 50000), step=100)
    if st.button("Descargar y analizar", type="primary"):
        with st.spinner("Descargando datos públicos y generando reportes..."):
            ok, output = run_analysis(departamento_input.strip(), municipio_input.strip(), int(limit_input))
        if ok:
            st.success("Análisis generado.")
        else:
            st.error("No se pudo completar el análisis.")
        with st.expander("Salida del proceso"):
            st.code(output)

run = read_current_run()
if not run:
    st.info("Escoge departamento y ciudad/municipio en la barra lateral y pulsa Descargar y analizar. Por defecto queda Bogotá, sin descargar información hasta que ejecutes el análisis.")
    st.stop()

st.caption(f"Último análisis: {run.get('municipio')} / {run.get('departamento')} · {run.get('registros_analizados', 0):,} registros")
df = load_data(run)
if df.empty:
    st.warning("No hay datos procesados para el último análisis.")
    st.stop()

df["valor_analisis"] = pd.to_numeric(df.get("valor_analisis", 0), errors="coerce").fillna(0)
df["score_riesgo"] = pd.to_numeric(df.get("score_riesgo", 0), errors="coerce").fillna(0)
df["secop"] = df.get("documentos_o_url", pd.Series(dtype=str)).map(linkify)

entity_options = sorted([x for x in df.get("entidad", pd.Series(dtype=str)).dropna().unique() if x])
modality_options = sorted([x for x in df.get("modalidad", pd.Series(dtype=str)).dropna().unique() if x])
risk_options = ["Bajo", "Medio", "Alto", "Crítico"]

with st.sidebar:
    st.header("Filtros")
    selected_entity = st.selectbox("Entidad", ["Todas"] + entity_options)
    selected_modality = st.selectbox("Modalidad", ["Todas"] + modality_options)
    selected_risk = st.multiselect("Nivel de riesgo", risk_options, default=risk_options)

filtered = df.copy()
if selected_entity != "Todas":
    filtered = filtered[filtered["entidad"] == selected_entity]
if selected_modality != "Todas":
    filtered = filtered[filtered["modalidad"] == selected_modality]
if selected_risk:
    filtered = filtered[filtered["nivel_riesgo"].isin(selected_risk)]

tab_general, tab_expedientes = st.tabs(["Alertas", "Expedientes"])

top_cols = [
    "expediente_id", "caso_id", "id_registro", "fuente", "entidad", "proveedor", "valor_estimado",
    "valor_adjudicado", "valor_analisis", "modalidad", "estado", "fecha", "score_riesgo",
    "nivel_riesgo", "tipo_alerta", "evidencia_minima", "secop",
]

with tab_general:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Registros analizados", f"{len(filtered):,}")
    col2.metric("Valor total analizado", f"${filtered['valor_analisis'].sum():,.0f}")
    col3.metric("Proveedores únicos", f"{filtered.get('proveedor_norm', pd.Series(dtype=str)).replace('', pd.NA).nunique():,}")
    col4.metric("Alertas altas", f"{int((filtered.get('nivel_riesgo') == 'Alto').sum()):,}")
    col5.metric("Alertas críticas", f"{int((filtered.get('nivel_riesgo') == 'Crítico').sum()):,}")

    st.subheader("Top riesgo")
    st.write(
        filtered.sort_values("score_riesgo", ascending=False)[[c for c in top_cols if c in filtered.columns]].head(20)
        .to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    st.subheader("Top valor")
    st.write(
        filtered.sort_values("valor_analisis", ascending=False)[[c for c in top_cols if c in filtered.columns]].head(20)
        .to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        entity_chart = (
            filtered.groupby("entidad", dropna=False)
            .size()
            .reset_index(name="registros")
            .sort_values("registros", ascending=False)
            .head(15)
        )
        st.plotly_chart(px.bar(entity_chart, x="registros", y="entidad", orientation="h", title="Registros por entidad"), use_container_width=True)

    with right:
        modality_chart = (
            filtered.groupby("modalidad", dropna=False)["valor_analisis"]
            .sum()
            .reset_index()
            .sort_values("valor_analisis", ascending=False)
            .head(15)
        )
        st.plotly_chart(px.bar(modality_chart, x="modalidad", y="valor_analisis", title="Valor por modalidad"), use_container_width=True)

    for label, column in (("Posibles procesos repetidos", "procesos_repetidos"), ("Posible fraccionamiento", "posible_fraccionamiento")):
        st.subheader(label)
        subset = filtered[filtered.get(column, False).astype(str).str.lower().isin(["true", "1", "si"])]
        st.write(
            subset.sort_values("score_riesgo", ascending=False)[[c for c in top_cols if c in subset.columns]].head(50)
            .to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

    excel_path = Path(run.get("excel", ""))
    if excel_path.exists():
        st.download_button(
            "Descargar Excel generado",
            data=excel_path.read_bytes(),
            file_name=excel_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with tab_expedientes:
    expedientes = load_expedientes(run)
    if expedientes.empty:
        st.warning("No se ha generado el Excel de expedientes.")
    else:
        critical = expedientes[expedientes["nivel_riesgo"].eq("Crítico")]
        c1, c2, c3 = st.columns(3)
        c1.metric("Expedientes", f"{len(expedientes):,}")
        c2.metric("Expedientes críticos", f"{len(critical):,}")
        c3.metric("Registros relacionados", f"{int(expedientes['cantidad_registros'].sum()):,}")

        expediente_cols = [
            "expediente_id", "nivel_riesgo", "score_max", "entidad", "proveedor",
            "valor_analisis_total", "fechas_relevantes", "registros_relacionados",
            "enlaces_secop", "documentos_faltantes", "recomendacion",
        ]
        st.subheader("Expedientes críticos")
        st.dataframe(critical[[c for c in expediente_cols if c in critical.columns]], use_container_width=True)

        st.subheader("Expedientes priorizados")
        st.dataframe(expedientes[[c for c in expediente_cols if c in expedientes.columns]], use_container_width=True)

        selected = st.selectbox("Ver detalle de expediente", expedientes["expediente_id"].tolist())
        detail = expedientes[expedientes["expediente_id"].eq(selected)].iloc[0]
        st.markdown(f"**Links SECOP:** {detail.get('enlaces_secop', '')}")
        st.markdown(f"**Documentos faltantes:** {detail.get('documentos_faltantes', '')}")
        st.markdown(f"**Recomendación:** {detail.get('recomendacion', '')}")

        related = filtered[filtered.get("expediente_id", "").eq(selected)]
        st.subheader("Registros relacionados")
        st.dataframe(related[[c for c in top_cols if c in related.columns]], use_container_width=True)

        expedientes_path = Path(run.get("expedientes_excel", ""))
        if expedientes_path.exists():
            st.download_button(
                "Descargar expedientes preliminares",
                data=expedientes_path.read_bytes(),
                file_name=expedientes_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
