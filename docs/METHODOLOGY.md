# Metodología

## Fuentes iniciales

- SECOP II - Contratos Electrónicos: `jbjy-vk9h`
- SECOP II - Procesos de Contratación: `p6dx-8zbt`

## Flujo de análisis

1. Descarga de datos públicos.
2. Limpieza y normalización.
3. Cálculo de campos estándar.
4. Cálculo de valor de análisis.
5. Aplicación de reglas de riesgo.
6. Construcción de expedientes preliminares.
7. Generación de reportes.

## Valor de análisis

Para procesos se usa `precio_base` como valor estimado. Si existe `valor_total_adjudicacion` mayor a cero, se conserva como valor adjudicado. Para contratos se usa `valor_del_contrato`.

El campo `valor_analisis` prioriza el valor adjudicado cuando existe y es mayor a cero; de lo contrario usa el valor estimado. Esta regla permite comparar procesos no adjudicados y contratos formalizados sin perder trazabilidad del origen de cada valor.

## Reglas de scoring

El scoring de riesgo contractual usa reglas heurísticas iniciales sobre señales documentales:

- Top 10% por valor.
- Top 5% por valor.
- Valor mayor a 100M.
- Contratación directa.
- Régimen especial repetido.
- Baja competencia.
- Procesos repetidos.
- Posible fraccionamiento.
- Cancelado/republicado.
- Objeto contractual genérico.
- Falta de datos críticos.

## Niveles de riesgo

- 0 a 30: Bajo
- 31 a 60: Medio
- 61 a 80: Alto
- 81 a 100: Crítico

## Expedientes preliminares

Los expedientes agrupan registros relacionados por:

- identificadores SECOP;
- referencias de proceso o contrato;
- URL o `noticeUID`;
- entidad;
- proveedor;
- objeto similar;
- valores cercanos;
- fechas cercanas.

Cada expediente preliminar organiza evidencia verificable, enlaces oficiales, razones de alerta, registros relacionados y documentos faltantes esperados. Su finalidad es facilitar revisión documental y priorización de casos, no declarar responsabilidad.

## Limitaciones

El análisis depende de la calidad de los datos publicados. Pueden existir falsos positivos, campos incompletos, nombres no normalizados, cambios de esquema o ausencia de documentos en las fuentes públicas.

El scoring es heurístico y los hallazgos requieren revisión humana. La herramienta no declara responsabilidad penal, fiscal, disciplinaria o administrativa, ni afirma corrupción confirmada.
