# Plataforma de Inteligencia Contractual Pública

Proyecto independiente de análisis de riesgo contractual basado en datos públicos del SECOP. No está afiliado, respaldado ni operado por Colombia Compra Eficiente ni por ninguna entidad estatal.

## Propósito

Construir una plataforma de inteligencia pública capaz de seguir el rastro del dinero estatal, detectar patrones graves de riesgo contractual y convertir datos públicos dispersos en evidencia organizada, trazable y difícil de ignorar.

La herramienta busca que la corrupción contractual sea más visible, más documentable y menos fácil de ocultar entre trámites, PDFs, procesos repetidos, baja competencia y silencio institucional.

No reemplaza a jueces, contralorías, procuradurías ni fiscalías. Su función es generar alertas, expedientes preliminares y evidencia verificable para revisión, denuncia o traslado a autoridad competente.

## Introducción

La plataforma descarga datos públicos de SECOP II desde datos.gov.co, limpia y normaliza información contractual, calcula un scoring de riesgo, identifica patrones anómalos y genera reportes técnicos para análisis territorial por departamento y ciudad/municipio.

Además, relaciona procesos y contratos, extrae enlaces oficiales, construye expedientes preliminares y permite priorizar casos con indicios documentales para revisión documental o eventual traslado a autoridad competente.

## Fuentes iniciales

- SECOP II - Contratos Electrónicos: `jbjy-vk9h`
- SECOP II - Procesos de Contratación: `p6dx-8zbt`

La herramienta trabaja con datos públicos y evita scraping frágil. Cada análisis debe interpretarse como insumo técnico preliminar, no como conclusión jurídica.

## Documentación del proyecto

- [Visión](docs/VISION.md)
- [Metodología](docs/METHODOLOGY.md)
- [Aviso legal](DISCLAIMER.md)
- [Roadmap](ROADMAP.md)
- [Seguridad](SECURITY.md)

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
- Objeto contractual genérico y falta de datos críticos.

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

El repositorio está preparado para GitHub. `.gitignore` excluye datos crudos, outputs, ZIPs, logs y cachés. Cada usuario clona el proyecto y genera sus propios datos localmente según el territorio elegido.

## Uso responsable

Los resultados son alertas técnicas e indicios documentales. No constituyen declaración de corrupción confirmada ni de responsabilidad penal, fiscal, disciplinaria o administrativa. Todo hallazgo requiere revisión documental, análisis jurídico y procedimiento institucional correspondiente.

## Limitaciones

El análisis depende de la calidad, completitud y actualización de los datos publicados. Pueden existir falsos positivos o información incompleta. Las reglas son heurísticas iniciales y no reemplazan auditorías, investigaciones oficiales ni decisiones de autoridad competente.
