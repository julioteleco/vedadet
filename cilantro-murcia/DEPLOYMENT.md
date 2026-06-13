# Guía de despliegue — Cilantro Murcia

Esta guía cubre cómo poner en marcha el backend (API + motor agronómico + UI web)
en otro entorno. La app móvil nativa **no** está incluida (ver `PENDIENTE.md`); el
cliente web servido en `/` cumple el flujo completo y sirve de referencia.

> **Filosofía:** sin ninguna configuración la app ya funciona (SQLite + Open-Meteo
> + climatología de Murcia + explicaciones de plantilla). Cada variable de entorno
> añade una capa opcional (PostgreSQL, LLM, SIAR/AEMET, push).

---

## 0. Requisitos

- Python 3.11+ (probado en 3.11)
- Opcional: Docker + Docker Compose (para el stack con PostgreSQL/PostGIS)
- Acceso de red saliente a `api.open-meteo.com` (si no, usa climatología local)

---

## 1. Despliegue local (rápido, SQLite)

```bash
cd cilantro-murcia
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# (opcional) configurar entorno
cp .env.example .env        # edita lo que quieras; nada es obligatorio

# arrancar la API + UI web
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- UI web:  http://localhost:8000/
- API docs: http://localhost:8000/docs
- La base de datos SQLite (`cilantro.db`) se crea sola al arrancar.

### Cargar variables del .env

`uvicorn` no lee `.env` automáticamente. Opciones:

```bash
# opción A: exportar a mano
export $(grep -v '^#' .env | xargs)

# opción B: usar python-dotenv (añádelo a requirements si lo quieres)
#   y un arranque que cargue dotenv, o:
uvicorn app.main:app --env-file .env       # uvicorn >= 0.21 soporta --env-file
```

### Comprobar que funciona

```bash
python -m cli.demo                 # demo offline de todo el motor
python -m pytest -q                # 46 tests
curl localhost:8000/health
```

---

## 2. Despliegue con Docker (stack completo + PostgreSQL/PostGIS)

```bash
cd cilantro-murcia
# (opcional) exporta claves antes si las tienes:
#   export ANTHROPIC_API_KEY=...  SIAR_API_KEY=...  AEMET_API_KEY=...
docker compose up --build
```

Esto levanta:
- `db`: PostgreSQL 16 + PostGIS 3.4 (volumen persistente `pgdata`)
- `api`: la app FastAPI en el puerto 8000, ya apuntando a `db`

La API crea las tablas al arrancar (`init_db()` en el lifespan).

Para inyectar las claves opcionales, descomenta las líneas correspondientes en
`docker-compose.yml` (sección `api > environment`) o pásalas por `.env` de Compose.

---

## 3. Despliegue gestionado (Cloud Run / Fly.io / similar)

El `Dockerfile` produce una imagen lista para cualquier PaaS de contenedores:

```bash
docker build -t cilantro-murcia .
# subir a tu registro y desplegar; configurar variables de entorno en el panel.
```

Pasos típicos:
1. Provisiona una base de datos PostgreSQL gestionada y define `DATABASE_URL`
   (`postgresql+psycopg://...`). Recuerda instalar el driver: descomenta
   `psycopg[binary]` en `requirements.txt`.
2. Define las claves opcionales (`ANTHROPIC_API_KEY`, `SIAR_API_KEY`,
   `AEMET_API_KEY`) como secretos.
3. Despliega la imagen; expón el puerto 8000.
4. Programa el job diario (`python -m app.jobs`) con el scheduler de la
   plataforma (Cloud Scheduler, cron de Fly machines, etc.).

---

## 4. Job diario (alertas automáticas)

Recorre los ciclos activos, avanza GDD/etapa, genera alertas y notifica:

```bash
python -m app.jobs
```

Programar a diario (ejemplo cron a las 07:00):

```cron
0 7 * * *  cd /ruta/cilantro-murcia && /ruta/.venv/bin/python -m app.jobs
```

---

## 5. Base de datos: SQLite vs PostgreSQL/PostGIS

- **SQLite** (por defecto): perfecto para desarrollo y demos. Un único fichero.
- **PostgreSQL/PostGIS**: para producción. Solo cambia `DATABASE_URL` e instala
  el driver `psycopg`. El esquema es agnóstico (lat/lon como floats); para
  consultas geoespaciales avanzadas se puede añadir una columna `geometry(Point,
  4326)` derivada por trigger sin tocar el motor.

No hay migraciones (Alembic) todavía: las tablas se crean con `init_db()`. Para
producción con esquema cambiante, añade Alembic (ver `PENDIENTE.md`).

---

## 6. Configuración agronómica (calibración por el experto)

Todas las constantes viven en `config/agronomy.yaml` y `config/varieties.yaml`,
versionadas. Un agrónomo puede editarlas **sin tocar código** y reiniciar la API.

El bucle de calibración (`POST /calibracion/run`) genera
`config/calibration_local.yaml` con propuestas a partir de observaciones reales;
revísalas y traslada los valores aceptados a `agronomy.yaml`.

---

## 7. Variables de entorno (resumen)

| Variable | Obligatoria | Efecto si falta |
|---|---|---|
| `DATABASE_URL` | No | usa SQLite `cilantro.db` |
| `ANTHROPIC_API_KEY` | No | explicaciones de plantilla (sin LLM) |
| `SIAR_API_KEY` | No | sin calibración SIAR de ET0 |
| `AEMET_API_KEY` | No | sin override oficial de helada |
| `FCM_CREDENTIALS` | No | push por consola (no envía a móviles) |

Ver `.env.example` para el detalle.

---

## 8. Solución de problemas

- **`no such table: ...`** → la app crea tablas en el arranque (lifespan). Si
  usas la API sin pasar por el arranque normal, llama a `app.db.init_db()`.
- **Open-Meteo da 403 / sin red** → es normal en entornos sin salida a internet;
  el motor cae a la climatología de Murcia automáticamente (no rompe nada).
- **PostgreSQL no conecta** → revisa `DATABASE_URL` y que el driver `psycopg`
  esté instalado (`pip install "psycopg[binary]"`).
