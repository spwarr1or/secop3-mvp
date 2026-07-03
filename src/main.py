from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from clean_data import clean_dataset
from config import make_run_config, output_files
from expediente_builder import generate_expediente_outputs
from fetch_secop import fetch_target_dataset, save_schema
from report_generator import generate_excel, generate_markdown
from risk_engine import score_risk


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SECOP 3.0 MVP parametrizable por municipio/departamento")
    parser.add_argument("--departamento", type=str, default=None, help="Departamento objetivo, por ejemplo Distrito Capital de Bogotá")
    parser.add_argument("--municipio", type=str, default=None, help="Ciudad o municipio objetivo, por ejemplo Bogotá")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de registros por dataset")
    parser.add_argument("--config", type=Path, default=None, help="Archivo YAML/JSON con departamento, municipio y límite")
    parser.add_argument("--skip-download", action="store_true", help="Reservado para una futura ejecución desde caché")
    return parser.parse_args()


def run_pipeline(run_config) -> dict[str, object]:
    files = output_files(run_config)

    contratos_raw = fetch_target_dataset(
        "contratos",
        municipio=run_config.municipio,
        departamento=run_config.departamento,
        limit=run_config.limit,
    )
    procesos_raw = fetch_target_dataset(
        "procesos",
        municipio=run_config.municipio,
        departamento=run_config.departamento,
        limit=run_config.limit,
    )

    schema = {
        "territorio": {
            "departamento": run_config.departamento,
            "municipio": run_config.municipio,
            "slug": run_config.slug,
        },
        "contratos": {
            "rows": len(contratos_raw),
            "columns": list(contratos_raw.columns),
            "dtypes": {column: str(dtype) for column, dtype in contratos_raw.dtypes.items()},
        },
        "procesos": {
            "rows": len(procesos_raw),
            "columns": list(procesos_raw.columns),
            "dtypes": {column: str(dtype) for column, dtype in procesos_raw.dtypes.items()},
        },
    }
    save_schema(schema, files["schema"])

    contratos_clean = clean_dataset(contratos_raw, "contratos")
    procesos_clean = clean_dataset(procesos_raw, "procesos")

    combined = pd.concat([contratos_clean, procesos_clean], ignore_index=True)
    scored = score_risk(combined)
    expedientes, related_scored = generate_expediente_outputs(
        scored,
        files["expedientes_excel"],
        files["expedientes_dir"],
    )
    scored = related_scored

    contratos_scored = scored[scored["fuente"] == "contratos"].copy()
    procesos_scored = scored[scored["fuente"] == "procesos"].copy()

    contratos_scored.to_csv(files["contratos_csv"], index=False, encoding="utf-8-sig")
    procesos_scored.to_csv(files["procesos_csv"], index=False, encoding="utf-8-sig")

    generate_excel(contratos_scored, procesos_scored, scored, files["excel"])
    generate_markdown(scored, files["markdown"], run_config.municipio, run_config.departamento)

    result = {
        "departamento": run_config.departamento,
        "municipio": run_config.municipio,
        "slug": run_config.slug,
        "contratos_limpios": str(files["contratos_csv"]),
        "procesos_limpios": str(files["procesos_csv"]),
        "excel": str(files["excel"]),
        "expedientes_excel": str(files["expedientes_excel"]),
        "expedientes_markdown_dir": str(files["expedientes_dir"]),
        "markdown": str(files["markdown"]),
        "schema": str(files["schema"]),
        "registros_analizados": len(scored),
        "expedientes_generados": len(expedientes),
    }
    files["current_run"].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    args = parse_args()
    if args.skip_download:
        raise SystemExit("--skip-download aún no está implementado para mantener trazabilidad de datos crudos.")

    run_config = make_run_config(
        departamento=args.departamento,
        municipio=args.municipio,
        limit=args.limit,
        config_path=args.config,
    )
    result = run_pipeline(run_config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
