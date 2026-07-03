from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
OUTPUTS_DIR = ROOT_DIR / "outputs"

for directory in (RAW_DIR, PROCESSED_DIR, REPORTS_DIR, OUTPUTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / ".env")

SOCRATA_BASE_URL = "https://www.datos.gov.co/resource"
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "").strip()
DEFAULT_LIMIT = int(os.getenv("SECOP_LIMIT", "50000"))
DEFAULT_MUNICIPALITY = os.getenv("SECOP_MUNICIPIO", "Bogotá")
DEFAULT_DEPARTMENT = os.getenv("SECOP_DEPARTAMENTO", "Distrito Capital de Bogotá")

DATASETS = {
    "contratos": {
        "id": "jbjy-vk9h",
        "endpoint": f"{SOCRATA_BASE_URL}/jbjy-vk9h.json",
        "city_col": "ciudad",
        "department_col": "departamento",
        "entity_col": "nombre_entidad",
    },
    "procesos": {
        "id": "p6dx-8zbt",
        "endpoint": f"{SOCRATA_BASE_URL}/p6dx-8zbt.json",
        "city_col": "ciudad_entidad",
        "department_col": "departamento_entidad",
        "entity_col": "entidad",
    },
}

LEGAL_NOTE = (
    "Este análisis no declara corrupción ni responsabilidad penal, fiscal o disciplinaria. "
    "Identifica señales de riesgo basadas en datos públicos que pueden justificar revisión, "
    "denuncia o traslado a autoridad competente."
)

REVIEW_RECOMMENDATION = (
    "Caso con evidencia suficiente para revisión o traslado a autoridad competente; presenta "
    "indicios documentales de riesgo contractual y requiere revisión."
)


@dataclass(frozen=True)
class RunConfig:
    departamento: str
    municipio: str
    limit: int = DEFAULT_LIMIT

    @property
    def slug(self) -> str:
        return slugify(f"{self.municipio}_{self.departamento}")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug or "territorio"


def output_files(run_config: RunConfig) -> dict[str, Path]:
    slug = run_config.slug
    return {
        "contratos_csv": OUTPUTS_DIR / f"{slug}_contratos_limpios.csv",
        "procesos_csv": OUTPUTS_DIR / f"{slug}_procesos_limpios.csv",
        "excel": OUTPUTS_DIR / f"{slug}_secop3_alertas_riesgo.xlsx",
        "expedientes_excel": OUTPUTS_DIR / f"{slug}_expedientes_preliminares.xlsx",
        "expedientes_dir": OUTPUTS_DIR / "expedientes" / slug,
        "markdown": OUTPUTS_DIR / f"{slug}_radiografia_contractual.md",
        "schema": OUTPUTS_DIR / f"{slug}_schema_detected.json",
        "current_run": OUTPUTS_DIR / "current_run.json",
    }


def load_config_file(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML no está instalado. Ejecuta: pip install -r requirements.txt")
        data = yaml.safe_load(text) or {}
    else:
        import json

        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("El archivo de configuración debe contener un objeto clave/valor.")
    return data


def make_run_config(
    departamento: str | None = None,
    municipio: str | None = None,
    limit: int | None = None,
    config_path: Path | None = None,
) -> RunConfig:
    data = load_config_file(config_path)
    return RunConfig(
        departamento=departamento or data.get("departamento") or DEFAULT_DEPARTMENT,
        municipio=municipio or data.get("municipio") or DEFAULT_MUNICIPALITY,
        limit=int(limit or data.get("limite") or data.get("limit") or DEFAULT_LIMIT),
    )
