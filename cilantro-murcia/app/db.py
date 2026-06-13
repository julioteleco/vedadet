"""Capa de persistencia (SQLAlchemy 2.0).

Modelo de datos de la PARTE 2-C. Por defecto usa SQLite (cero configuración);
apunta a PostgreSQL/PostGIS definiendo DATABASE_URL.

  export DATABASE_URL=postgresql+psycopg://user:pass@host/cilantro

La geometría se guarda como lat/lon flotantes (portable). En PostGIS se puede
añadir una columna `geometry(Point,4326)` derivada por trigger; el motor solo
necesita lat/lon, así que el código es agnóstico de la BD.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (DateTime, Float, ForeignKey, String, create_engine,
                        func)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///cilantro.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class Parcela(Base):
    __tablename__ = "parcela"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), default="Mi parcela")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    altitud_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tipo_suelo: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    ph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ec_agua_dS_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    microclima: Mapped[str] = mapped_column(String(20), default="valle")
    estacion_siar: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    municipio_ine: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ciclos: Mapped[list["CicloCultivo"]] = relationship(back_populates="parcela",
                                                        cascade="all, delete-orphan")


class CicloCultivo(Base):
    __tablename__ = "ciclo_cultivo"
    id: Mapped[int] = mapped_column(primary_key=True)
    parcela_id: Mapped[int] = mapped_column(ForeignKey("parcela.id"))
    variedad: Mapped[str] = mapped_column(String(40), default="Calypso")
    objetivo: Mapped[str] = mapped_column(String(10), default="hoja")  # hoja | semilla
    fecha_siembra: Mapped[date] = mapped_column()
    cosecha_prevista: Mapped[Optional[date]] = mapped_column(nullable=True)
    etapa: Mapped[str] = mapped_column(String(20), default="siembra")
    gdd_acum: Mapped[float] = mapped_column(Float, default=0.0)
    estado: Mapped[str] = mapped_column(String(20), default="activo")  # activo|cerrado

    parcela: Mapped["Parcela"] = relationship(back_populates="ciclos")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="ciclo",
                                                   cascade="all, delete-orphan")
    observaciones: Mapped[list["Observacion"]] = relationship(
        back_populates="ciclo", cascade="all, delete-orphan")


class Evento(Base):
    """EventoSiembra / EventoCosecha unificado por `tipo`."""
    __tablename__ = "evento"
    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo_cultivo.id"))
    tipo: Mapped[str] = mapped_column(String(20))  # siembra | cosecha
    fecha: Mapped[date] = mapped_column()
    cantidad: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nota: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    ciclo: Mapped["CicloCultivo"] = relationship(back_populates="eventos")


class Observacion(Base):
    """Observación fenológica REAL para el bucle de calibración (Recomendación #4).

    tipo: emergencia | primera_hoja | espigado | semilla
    Guarda GDD acumulados al observarse para recalibrar umbrales locales.
    """
    __tablename__ = "observacion"
    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclo_cultivo.id"))
    tipo: Mapped[str] = mapped_column(String(20))
    fecha: Mapped[date] = mapped_column()
    gdd_al_observar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tmax_al_observar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    nota: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    ciclo: Mapped["CicloCultivo"] = relationship(back_populates="observaciones")


class SnapshotMeteo(Base):
    __tablename__ = "snapshot_meteo"
    id: Mapped[int] = mapped_column(primary_key=True)
    parcela_id: Mapped[int] = mapped_column(ForeignKey("parcela.id"))
    fecha: Mapped[date] = mapped_column()
    tmax: Mapped[float] = mapped_column(Float)
    tmin: Mapped[float] = mapped_column(Float)
    precip: Mapped[float] = mapped_column(Float, default=0.0)
    et0: Mapped[float] = mapped_column(Float, default=0.0)
    fotoperiodo: Mapped[float] = mapped_column(Float, default=0.0)
    fuente: Mapped[str] = mapped_column(String(30), default="climatology")


class Alerta(Base):
    __tablename__ = "alerta"
    id: Mapped[int] = mapped_column(primary_key=True)
    parcela_id: Mapped[int] = mapped_column(ForeignKey("parcela.id"))
    ciclo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ciclo_cultivo.id"),
                                                    nullable=True)
    tipo: Mapped[str] = mapped_column(String(20))  # sembrar|regar|espigado|helada|cosecha
    severidad: Mapped[str] = mapped_column(String(10), default="media")
    mensaje: Mapped[str] = mapped_column(String(400))
    accion: Mapped[str] = mapped_column(String(400), default="")
    fecha_limite: Mapped[Optional[date]] = mapped_column(nullable=True)
    creada: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    enviada: Mapped[bool] = mapped_column(default=False)


def init_db():
    """Crea las tablas si no existen."""
    Base.metadata.create_all(engine)


def get_session():
    """Generador de sesión para dependencias FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
