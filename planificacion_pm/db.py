"""Base de datos SQLite: reemplaza las hojas Historial, Aceites, Lecturas, Programación,
Configuración, Kits PM, Descripciones y los formatos de solicitud de análisis."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .util import a_fecha, a_fechahora

ESQUEMA = """
CREATE TABLE IF NOT EXISTS historial (
    seq INTEGER PRIMARY KEY,           -- orden de la fila (como en la tabla de Excel)
    id INTEGER NOT NULL,               -- ID de la PM
    equipo TEXT NOT NULL, modelo TEXT, faena TEXT,
    tipo REAL, fecha TEXT, horo REAL, horas REAL, fprog TEXT, obs TEXT,
    reg_el TEXT, reg_por TEXT,
    pos INTEGER                        -- posición de la PM mayor en el ciclo del modelo
);
CREATE TABLE IF NOT EXISTS aceites (
    seq INTEGER PRIMARY KEY,
    id_pm INTEGER, equipo TEXT, comp TEXT, horo REAL, origen TEXT, reg_el TEXT,
    horas_ac                           -- número o texto «Sin cambio anterior»
);
CREATE TABLE IF NOT EXISTS lecturas (
    equipo TEXT PRIMARY KEY, horo REAL, fecha TEXT, por TEXT
);
CREATE TABLE IF NOT EXISTS programacion (
    equipo TEXT PRIMARY KEY, tipo REAL, horo_obj REAL, fecha TEXT, actualizado TEXT
);
CREATE TABLE IF NOT EXISTS config (
    clave TEXT PRIMARY KEY, valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plantillas (
    modelo TEXT PRIMARY KEY, datos BLOB NOT NULL
);
"""

# Parámetros (hoja Configuración, columna K)
PARAMS_DEF = [
    ("intervalo", "Intervalo entre PM (h)", 250),
    ("horas_dia", "Horas/día por defecto (sin historial suficiente)", 13),
    ("pm_prom", "N° de PM para promedio real h/día", 6),
    ("alerta_pm", "Alerta PM próxima (horas restantes)", 50),
    ("alerta_aceite", "Alerta aceite (% de la frecuencia)", 0.8),
    ("muestra", "Frecuencia toma de muestra aceite motor (h)", 100),
    ("tarro", "Litros por tarro", 208),
    ("margen", "Margen de seguridad compra de aceites", 0.2),
    ("margen_prog", "Margen de seguridad para programar PM (% de los días restantes)", 0.15),
    ("avance_extra", "Avance extra de horómetro proyectado (% sobre el promedio real h/día)", 0.15),
]


def _iso(v):
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, dt.date):
        return v.isoformat()
    return v


class Repositorio:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(str(self.ruta))
        self.cx.row_factory = sqlite3.Row
        self.cx.executescript(ESQUEMA)
        self.cx.commit()

    def cerrar(self):
        self.cx.close()

    @contextmanager
    def transaccion(self):
        try:
            yield self.cx
            self.cx.commit()
        except Exception:
            self.cx.rollback()
            raise

    # ------------------------------------------------------------------ config
    def vacia(self) -> bool:
        return self.cx.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0

    def get_config(self, clave: str, defecto=None):
        r = self.cx.execute("SELECT valor FROM config WHERE clave=?", (clave,)).fetchone()
        return json.loads(r[0]) if r else defecto

    def set_config(self, clave: str, valor, commit: bool = True):
        self.cx.execute("INSERT OR REPLACE INTO config(clave, valor) VALUES(?,?)",
                        (clave, json.dumps(valor, ensure_ascii=False, default=_iso)))
        if commit:
            self.cx.commit()

    def params(self) -> dict:
        p = {k: v for k, _, v in PARAMS_DEF}
        p.update(self.get_config("params", {}))
        return p

    # --------------------------------------------------------------- historial
    def historial(self) -> list[dict]:
        out = []
        for r in self.cx.execute("SELECT * FROM historial ORDER BY seq"):
            d = dict(r)
            d["fecha"] = a_fecha(d["fecha"])
            d["fprog"] = a_fecha(d["fprog"])
            d["reg_el"] = a_fechahora(d["reg_el"])
            out.append(d)
        return out

    def agregar_historial(self, fila: dict) -> int:
        seq = (self.cx.execute("SELECT COALESCE(MAX(seq),0)+1 FROM historial").fetchone()[0])
        cols = ["seq", "id", "equipo", "modelo", "faena", "tipo", "fecha", "horo", "horas",
                "fprog", "obs", "reg_el", "reg_por", "pos"]
        fila = dict(fila, seq=seq)
        self.cx.execute(f"INSERT INTO historial({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                        [_iso(fila.get(c)) for c in cols])
        return seq

    def actualizar_historial(self, seq: int, campos: dict):
        sets = ",".join(f"{k}=?" for k in campos)
        self.cx.execute(f"UPDATE historial SET {sets} WHERE seq=?", [_iso(v) for v in campos.values()] + [seq])

    def borrar_historial(self, seq: int):
        self.cx.execute("DELETE FROM historial WHERE seq=?", (seq,))

    # ----------------------------------------------------------------- aceites
    def aceites(self) -> list[dict]:
        out = []
        for r in self.cx.execute("SELECT * FROM aceites ORDER BY seq"):
            d = dict(r)
            d["reg_el"] = a_fechahora(d["reg_el"])
            out.append(d)
        return out

    def agregar_aceite(self, fila: dict):
        cols = ["id_pm", "equipo", "comp", "horo", "origen", "reg_el", "horas_ac"]
        self.cx.execute(f"INSERT INTO aceites({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                        [_iso(fila.get(c)) for c in cols])

    def actualizar_aceite(self, seq: int, campos: dict):
        sets = ",".join(f"{k}=?" for k in campos)
        self.cx.execute(f"UPDATE aceites SET {sets} WHERE seq=?", [_iso(v) for v in campos.values()] + [seq])

    def borrar_aceite(self, seq: int):
        self.cx.execute("DELETE FROM aceites WHERE seq=?", (seq,))

    # ------------------------------------------------------ lecturas / program.
    def lecturas(self) -> dict:
        return {r["equipo"]: {"horo": r["horo"], "fecha": a_fecha(r["fecha"]), "por": r["por"]}
                for r in self.cx.execute("SELECT * FROM lecturas")}

    def set_lectura(self, equipo, horo, fecha, por):
        self.cx.execute("INSERT OR REPLACE INTO lecturas(equipo, horo, fecha, por) VALUES(?,?,?,?)",
                        (equipo, horo, _iso(fecha), por))

    def programacion(self) -> dict:
        return {r["equipo"]: {"tipo": r["tipo"], "horo_obj": r["horo_obj"], "fecha": a_fecha(r["fecha"]),
                              "actualizado": a_fechahora(r["actualizado"])}
                for r in self.cx.execute("SELECT * FROM programacion")}

    def set_programacion(self, equipo, tipo, horo_obj, fecha, actualizado):
        self.cx.execute("INSERT OR REPLACE INTO programacion(equipo, tipo, horo_obj, fecha, actualizado) "
                        "VALUES(?,?,?,?,?)", (equipo, tipo, horo_obj, _iso(fecha), _iso(actualizado)))

    # -------------------------------------------------------------- plantillas
    def plantilla(self, modelo: str) -> bytes | None:
        r = self.cx.execute("SELECT datos FROM plantillas WHERE modelo=?", (modelo,)).fetchone()
        return bytes(r[0]) if r else None

    def set_plantilla(self, modelo: str, datos: bytes):
        self.cx.execute("INSERT OR REPLACE INTO plantillas(modelo, datos) VALUES(?,?)", (modelo, datos))

    def modelos_plantilla(self) -> list[str]:
        return [r[0] for r in self.cx.execute("SELECT modelo FROM plantillas ORDER BY modelo")]

    # ------------------------------------------------------------------ limpiar
    def vaciar_todo(self):
        for t in ("historial", "aceites", "lecturas", "programacion", "config", "plantillas"):
            self.cx.execute(f"DELETE FROM {t}")
