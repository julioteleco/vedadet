# 🌿 Cilantro Murcia — Motor agronómico determinista + IA

App de cultivo de cilantro (*Coriandrum sativum*) para la Región de Murcia.
Implementa la **v1 del núcleo determinista** descrito en la especificación
agronómica: GDD, fotoperiodo, riesgo de espigado (*bolting*), riego ET0 (FAO-56)
y helada, más un **optimizador de ventana de siembra**. La IA (LLM) se usa
**estrictamente aguas abajo** para explicar los números; nunca los calcula.

> **Principio de diseño:** toda la agronomía son algoritmos deterministas
> anclados en constantes con fuente (un único YAML versionado). El LLM solo
> traduce las salidas a lenguaje llano. Esto evita alucinaciones en los cálculos.

## Por qué este alcance

La Recomendación #1 de la especificación: *"Lanza la v1 solo con el núcleo
determinista usando Open-Meteo como única fuente y Santo/Calypso como defaults.
Ya da a un usuario sin conocimientos un cultivo de otoño–invierno creíble."*

## Estructura

```
cilantro-murcia/
├── config/
│   ├── agronomy.yaml        # TODAS las constantes (calibrables sin tocar código)
│   └── varieties.yaml       # cultivares + offset de resistencia al espigado
├── app/
│   ├── engine/              # MOTOR DETERMINISTA (toda la agronomía)
│   │   ├── photoperiod.py   # fotoperiodo desde latitud + día del año
│   │   ├── gdd.py           # GDD (Tbase 4°C, corte 30°C) + etapas
│   │   ├── bolting.py       # score de riesgo de espigado 0-100
│   │   ├── irrigation.py    # ETc = Kc·ET0, balance hídrico, Hargreaves
│   │   ├── frost.py         # alertas de helada
│   │   └── sowing_window.py # optimizador + plan escalonado
│   ├── weather/openmeteo.py # fuente meteo primaria (ET0 FAO + forecast)
│   ├── data/                # normales climáticas de Murcia (fallback offline)
│   ├── llm.py               # explicación LLM (solo downstream; opcional)
│   ├── models.py            # entidades (Pydantic) — PARTE 2-C
│   ├── service.py           # orquestación meteo + motor + LLM
│   └── main.py              # API FastAPI
├── cli/demo.py              # demo OFFLINE de todo el motor
└── tests/                   # 32 tests del motor
```

## Instalación

```bash
cd cilantro-murcia
pip install -r requirements.txt
```

(El núcleo y la CLI solo necesitan `PyYAML`; el resto es para API/LLM/meteo.)

## Uso

### 1. Demo offline (sin red, recomendado para empezar)

```bash
python -m cli.demo
```

Imprime el fotoperiodo anual a 38°N, el riesgo de espigado mes a mes, la mejor
ventana de siembra otoño–invierno con plan escalonado, y un ejemplo de riego.

### 2. API REST

```bash
uvicorn app.main:app --reload
# Documentación interactiva: http://localhost:8000/docs
```

Endpoints:

| Método | Ruta | Descripción |
|---|---|---|
| GET  | `/health` | estado + versión de config agronómica |
| GET  | `/varieties` | cultivares y su resistencia al espigado |
| POST | `/recommend/bolting` | riesgo de espigado hoy + acción |
| POST | `/recommend/irrigation` | L/m² a regar hoy (ET0·Kc) |
| POST | `/recommend/sowing` | mejor(es) fecha(s) de siembra + escalonado |

Ejemplo:

```bash
curl -X POST localhost:8000/recommend/sowing -H 'Content-Type: application/json' \
  -d '{"lat":37.98,"lon":-1.13,"variety":"Calypso","microclimate":"valle",
       "start":"2025-09-01","end":"2026-02-01","objetivo":"hoja"}'
```

### 3. Explicación con LLM (opcional)

Si defines `ANTHROPIC_API_KEY`, las respuestas incluyen una explicación en
lenguaje natural redactada por Claude **a partir de los números del motor**
(grounding). Sin la clave, se usa una plantilla determinista — la app funciona
igual.

## Integración meteorológica

- **Primaria: Open-Meteo** — `et0_fao_evapotranspiration` (Penman-Monteith
  FAO-56) + Tmax/Tmin/precip + forecast 16 días. Gratis, no comercial.
- **Fallback: climatología de Murcia** (1991–2020) si no hay red — el motor
  nunca se queda sin datos.
- **v2 (pendiente):** SIAR (ET0 local, estaciones del regadío de Murcia) y
  AEMET OpenData (predicción municipal + avisos oficiales de helada).

## Algoritmos (resumen)

| Algoritmo | Constantes clave | Fuente |
|---|---|---|
| Fotoperiodo | δ=23,45·sin(...), corrección −0,833° | astronómica |
| GDD | Tbase 4°C, corte 30°C | López-Urrea/Paredes 2025 |
| Bolting risk | T_bolt 24°C, DL_crit 12h, factor variedad | extensión *(calibrar)* |
| Riego | Kc 0,66/1,19/1,36/0,98 | Ghamarnia 2013 *(semilla)* |
| Helada | plántula ≤0°C alta; establecido ~−2°C | extensión |

## ⚠️ Banderas de calibración

Valores marcados `[ESTIMADO/CALIBRAR]` en `config/agronomy.yaml` (umbral de
espigado 24°C, fotoperiodo crítico 12 h, partición GDD-a-hoja, offsets de
cultivar, Kc de hoja, salinidad sin umbral publicado). **Todos son editables en
el YAML** y deben refinarse con observaciones en finca (Recomendación #4 de la
especificación). Fuerza la entrada de la EC del agua local en el onboarding.

## Tests

```bash
python -m pytest -q     # 32 tests
```

## Hoja de ruta

- [x] v1: núcleo determinista (GDD, fotoperiodo, espigado, riego, helada, ventana)
- [x] API FastAPI + CLI + grounding LLM opcional
- [ ] v2: SIAR + AEMET (ET0 local + helada oficial), PostgreSQL/PostGIS
- [ ] App móvil (Flutter/React Native) + push (FCM)
- [ ] Bucle de calibración: registrar emergencia/cosecha/espigado reales por ciclo
