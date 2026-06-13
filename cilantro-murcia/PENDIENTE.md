# Lo que falta / limitaciones conocidas — Cilantro Murcia

Documento honesto del estado del proyecto. Se divide en (A) lo que falta a nivel
de **software/ingeniería**, (B) lo que falta a nivel **agronómico/de datos**
(constantes que hay que calibrar en campo), y (C) limitaciones del **entorno**
en el que se construyó.

---

## A. Pendiente de software (no construido)

| Área | Estado | Qué falta exactamente |
|---|---|---|
| **App móvil nativa** | ❌ No construida | Flutter/React Native consumiendo esta API. El cliente web (`web/index.html`) cumple el flujo UX completo y sirve de referencia/contrato de la API, pero no hay binario móvil ni push real en dispositivo. |
| **Push real (FCM)** | ⚠️ Abstracción lista | `app/notifications.py` tiene el backend FCM, pero por defecto registra en consola. Falta: proyecto Firebase, credenciales de servicio y registro de tokens de dispositivo por usuario (no hay entidad `Usuario`/`Dispositivo`). |
| **Autenticación / multiusuario** | ❌ No construido | No hay login, ni usuarios, ni multi-tenant. Todas las parcelas son globales. Para producción: añadir auth (OAuth/JWT) y `owner_id` en las entidades. |
| **Migraciones de BD** | ❌ No construido | Las tablas se crean con `init_db()` (create_all). Falta Alembic para evolucionar el esquema sin perder datos. |
| **SIAR/AEMET en vivo** | ⚠️ Clientes listos, sin validar contra API real | El código y el patrón de dos pasos de AEMET están implementados, pero **no se han probado contra las APIs reales** (el entorno de desarrollo no tenía red ni claves). Hay que validar los nombres de campos del JSON real de SIAR (`EtPMon`, etc.) y ajustar si difieren. |
| **Catálogo SIAR/municipios completo** | ⚠️ Subset | Solo se incluyen ~6 estaciones SIAR y ~6 municipios INE de referencia. En producción cargar el catálogo completo vía el endpoint `/Estaciones` de SIAR y la tabla INE completa. |
| **Caché meteorológica** | ❌ No construido | Cada petición consulta la fuente. La PARTE 2-E pide caché; falta (p. ej. Redis o tabla `SnapshotMeteo` como caché con TTL). Ya se persisten snapshots, pero no se reutilizan como caché. |
| **Optimizador con forecast real** | ⚠️ Solo climatología | `sowing_window` simula con climatología de Murcia. La PARTE 2-A.5 pide mezclar forecast de Open-Meteo/AEMET en el horizonte cercano; falta esa fusión. |
| **Altitud → microclima fino** | ⚠️ Heurística | `onboarding.classify_microclimate` usa una heurística simple (lat/lon/altitud). No usa un modelo digital del terreno ni datos de heladas por pedanía. |
| **Observabilidad / logs estructurados** | ❌ No construido | Solo `logging` básico. Falta métricas, trazas y healthchecks avanzados para producción. |
| **Tests de integración meteo en vivo** | ❌ | Los tests cubren el fallback offline; no hay tests contra Open-Meteo/SIAR/AEMET reales (requieren red/claves). |
| **CI/CD** | ❌ No construido | No hay pipeline (GitHub Actions). Fácil de añadir: `pytest` ya pasa en limpio. |

---

## B. Pendiente agronómico — constantes a CALIBRAR en campo

Estos valores están en `config/agronomy.yaml` marcados `[ESTIMADO/CALIBRAR]`.
**Funcionan como defaults razonables pero NO están validados experimentalmente
para Murcia.** El bucle de calibración (`/calibracion/run`) los refina con
observaciones reales (Recomendación #4 del informe base).

| Constante | Valor default | Origen | Riesgo |
|---|---|---|---|
| `bolting.t_bolt` = 24 °C | umbral de espigado | nivel extensión, **no ensayo** | Si el cilantro espiga por debajo de 24 °C en tu finca, bájalo. |
| `bolting.dl_crit` = 12 h | fotoperiodo crítico | nivel extensión | Aproximado; ajustar con observación. |
| `gdd_stages.*` | 100/375/900/1500 | **sin partición publicada** hoja vs semilla | El GDD a hoja es el más incierto; calíbralo con la fecha real de primera cosecha. |
| `kc_sets.leaf_default` | 0,66/1,00/1,10/0,90 | transferido de ensayos de **semilla** (Ghamarnia 2013) | Un corte solo de hoja consume menos; curva truncada a calibrar. |
| `varieties[].bolt_factor` / `bolt_delay_days` | relativos a Santo | nivel extensión | Magnitudes aproximadas; el ranking (Calypso > Santo > Leisure) sí es fiable. |
| `salinity.ece_threshold_dS_m` = null | **sin umbral publicado** | Shannon & Grieve 1999 | No existe para cilantro. Por eso el onboarding **obliga a medir la EC del agua**. |

### Cómo cerrar estos huecos (flujo de calibración)
1. Registra observaciones reales por ciclo vía `POST /observaciones`
   (`emergencia`, `primera_hoja`, `espigado`, `semilla`), guardando GDD y/o Tmax.
2. Ejecuta `POST /calibracion/run` → genera `config/calibration_local.yaml` con
   propuestas (mediana de GDD por etapa, T_bolt observado, factores de variedad).
3. El experto revisa y traslada los valores aceptados a `config/agronomy.yaml`.

---

## C. Limitaciones del entorno de construcción

- **Sin red saliente:** el contenedor donde se desarrolló bloquea internet
  (Open-Meteo devolvía 403). Por eso todo el motor tiene **fallback a
  climatología de Murcia** y los clientes SIAR/AEMET no se pudieron validar
  contra las APIs reales. En un entorno con red, el `provider` usará las fuentes
  en vivo automáticamente.
- **Sin toolchain móvil ni nube:** no había SDK de Flutter/React Native ni
  credenciales de Cloud/Firebase, de ahí que la app móvil y el push real queden
  como pendientes (sección A).

---

## D. Lo que SÍ está completo y probado

- Motor determinista íntegro: fotoperiodo, GDD, espigado, riego ET0/Kc
  (+Hargreaves), helada, optimizador de ventana + escalonado.
- Persistencia (SQLAlchemy, SQLite/PostgreSQL-PostGIS) con todas las entidades.
- Onboarding (deriva microclima/SIAR/municipio, fuerza EC del agua).
- Motor de alertas + job diario + abstracción de push.
- Bucle de calibración.
- Clientes Open-Meteo/SIAR/AEMET con fallback elegante.
- API FastAPI completa + UI web.
- Docker + docker-compose (API + PostGIS).
- **46 tests pasando** (incluye fallback offline, persistencia y calibración).
