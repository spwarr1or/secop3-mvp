# SECOP 3.0 MVP

Herramienta en Python para analizar contratación pública en Colombia usando datos públicos de SECOP II desde datos.gov.co. El usuario elige departamento y ciudad/municipio; el sistema descarga la información, limpia datos, calcula alertas de riesgo contractual y genera reportes.

El lenguaje del proyecto es deliberadamente prudente: identifica indicios documentales y casos que requieren revisión de autoridad competente. No afirma corrupción confirmada ni responsabilidad penal, fiscal o disciplinaria.

## Fuentes

- SECOP II - Contratos Electrónicos: `jbjy-vk9h`
- SECOP II - Procesos de Contratación: `p6dx-8zbt`

No se usan datos privados ni scraping frágil.

## Instalación

```bash
pip install -r requirements.txt
```

Opcional: copia `.env.example` a `.env` y define `SOCRATA_APP_TOKEN` si tienes token de Socrata.

## Uso por consola

```bash
python src/main.py --departamento "Distrito Capital de Bogotá" --municipio "Bogotá"
```

Con límite de registros por dataset:

```bash
python src/main.py --departamento "Antioquia" --municipio "Medellín" --limit 50000
```

También puedes usar archivo de configuración:

```bash
cp config.example.yaml config.yaml
python src/main.py --config config.yaml
```

## Dashboard

```bash
streamlit run src/app_streamlit.py
```

Desde la barra lateral puedes escoger departamento en un menú desplegable y luego ciudad/municipio en un segundo menú que depende del departamento seleccionado. Por defecto queda Bogotá, pero no descarga información hasta que pulses el botón.

Para publicar en una IP privada sin tocar otros servicios HTTP, usa un puerto libre explícito:

```bash
streamlit run src/app_streamlit.py --server.address 192.168.40.7 --server.port 8503
```

## Salidas

Los archivos se generan en `outputs/` con prefijo del territorio, por ejemplo `cordoba_narino_*`:

- `<territorio>_contratos_limpios.csv`
- `<territorio>_procesos_limpios.csv`
- `<territorio>_secop3_alertas_riesgo.xlsx`
- `<territorio>_expedientes_preliminares.xlsx`
- `<territorio>_radiografia_contractual.md`
- `<territorio>_schema_detected.json`
- `outputs/expedientes/<territorio>/EXPEDIENTE_<id>_<riesgo>.md`
- `outputs/current_run.json`

Los datos crudos quedan en `data/raw/`.

## Campos de valor

- `valor_estimado`: para procesos usa `precio_base`; para contratos usa `valor_del_contrato`.
- `valor_adjudicado`: para procesos usa `valor_total_adjudicacion`; para contratos usa `valor_del_contrato`.
- `valor_analisis`: usa `valor_adjudicado` si es mayor a 0; si no, usa `valor_estimado`.
- `valor_num`: alias de compatibilidad de `valor_analisis`.

## Score de riesgo

El campo `score_riesgo` va de 0 a 100. Reglas principales:

- Top 10% por `valor_analisis`: +20.
- Top 5% por `valor_analisis`: +30.
- Procesos con valor mayor a 100M COP: +20.
- Procesos repetidos con objeto similar, misma entidad y fechas cercanas: +25.
- Contratación directa: +25.
- Régimen especial repetido con objeto similar: +15.
- Baja competencia: +10 o +15 según indicio.
- Cancelado/republicado con objeto similar: +20.
- Posible fraccionamiento sin comparar un proceso contra su propio contrato asociado: +25.

Clasificación:

- 0 a 30: Bajo
- 31 a 60: Medio
- 61 a 80: Alto
- 81 a 100: Crítico

## Expedientes preliminares

`src/expediente_builder.py` relaciona procesos y contratos por identificadores SECOP, referencias, URL, `noticeUID`, entidad, proveedor, objeto, valor y fechas cercanas.

Cada expediente preliminar incluye entidad, proveedor, objeto consolidado, valores totales, fechas relevantes, registros relacionados, enlaces SECOP, razones de alerta, nivel de riesgo, documentos faltantes y recomendación.

Documentos faltantes esperados:

- estudios previos
- CDP
- RP
- pliego/invitación
- ofertas
- acta de evaluación
- contrato firmado
- actas de modificación
- actas de pago
- acta de cancelación, si aplica

## Repositorio liviano

El repo está preparado para GitHub. `.gitignore` excluye datos crudos, outputs, ZIPs, logs y cachés. Cada usuario clona el proyecto y genera sus propios datos localmente según el territorio elegido.

## Limitaciones

El análisis depende de la calidad, completitud y actualización de los datos publicados. Las reglas son heurísticas iniciales y no reemplazan auditoría documental ni análisis jurídico, fiscal o disciplinario.
