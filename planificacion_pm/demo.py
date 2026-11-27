"""Datos de ejemplo ficticios para la versión de muestra (Mac). No contienen información real de la operación:
historial, horómetros, aceites, kits y números de parte son simulados."""
from __future__ import annotations

import datetime as dt
import random

from .db import PARAMS_DEF, Repositorio
from .motor import PRECIOS_DEFECTO
from .util import ORIGEN_FUERA, ORIGEN_NO, ORIGEN_PM

EQUIPOS = [("D10", "DI650i"), ("D11", "DI650i"), ("D14", "DR412i"), ("D15", "DR412i"), ("D16", "DR412i")]
FAENA = "Demo"
CICLOS = [
    {"modelo": "DI650i", "pos1": 500, "pos2": 1000, "pos3": 1500, "pos4": None, "largo": 3, "cierres": "1500,3000,5000"},
    {"modelo": "DR412i", "pos1": 500, "pos2": 1000, "pos3": 500, "pos4": 2000, "largo": 4, "cierres": "2000"},
]
TIPOS = [{"modelo": "DI650i", "tipos": "250,500,1000,1500"}, {"modelo": "DR412i", "tipos": "250,500,1000,2000"}]
ACEITES = {
    "DI650i": [("Aceite motor diésel", 250), ("Aceite cabezal de rotación", 250), ("Aceite compresor", 500),
               ("Aceite mando final derecho", 500), ("Aceite mando final izquierdo", 500),
               ("Aceite hidráulico", 1500), ("Refrigerante motor diésel", 1500)],
    "DR412i": [("Aceite motor diésel", 250), ("Aceite bomba de agua", 250), ("Reductor avance derecho", 250),
               ("Reductor avance izquierdo", 250), ("Aceite cabezal de rotación", 250), ("Aceite PTO", 500),
               ("Aceite mando final derecho", 500), ("Aceite mando final izquierdo", 500),
               ("Aceite compresor", 1000), ("Aceite hidráulico", 1000), ("Cubo fan derecho", 1000),
               ("Cubo fan izquierdo", 1000), ("Refrigerante motor diésel", 2000)],
}
TIPOS_CONSUMO = [250, 500, 1000, 1500, 2000, 3000, 5000]
# modelo, sistema, lubricante, parte, litros, tipos que consumen
CONSUMO = [
    ("DI650i", "Motor diésel", "MOBIL DELVAC MX 15W40", "LL-0001", 50, (250, 500, 1000, 1500, 3000, 5000)),
    ("DI650i", "Cabezal rotación", "Mobil SHC GEAR 320", "LL-0005", 25, (250, 500, 1000, 1500, 3000, 5000)),
    ("DI650i", "Compresor", "MOBIL SHC RARUS 46", "LL-0003", 150, (500, 1000, 1500, 3000, 5000)),
    ("DI650i", "Mando final der/izq (total)", "M. LUBE HD PLUS 75W90", "LL-0002", 10, (500, 1000, 1500, 3000, 5000)),
    ("DI650i", "Refrigerante", "MOBIL MINING COOLANT 50%", "LL-0007", 150, (1500, 3000, 5000)),
    ("DI650i", "Hidráulico", "Mobil DTE 10 EXCEL 46", "LL-0004", 400, (1500, 3000, 5000)),
    ("DR412i", "Motor diésel", "MOBIL DELVAC MX 15W40", "LL-0001", 150, (250, 500, 1000, 2000)),
    ("DR412i", "Bomba de agua", "MOBIL DELVAC MX 15W40", "LL-0001", 2, (250, 500, 1000, 2000)),
    ("DR412i", "Cabezal rotación", "M. LUBE HD PLUS 75W90", "LL-0002", 25, (250, 500, 1000, 2000)),
    ("DR412i", "Reductores de avance", "M. LUBE HD PLUS 75W90", "LL-0002", 20, (250, 500, 1000, 2000)),
    ("DR412i", "Mando final der/izq (total)", "M. LUBE HD PLUS 75W90", "LL-0002", 20, (500, 1000, 2000)),
    ("DR412i", "Caja de engranaje (PTO)", "M. LUBE HD PLUS 75W90", "LL-0002", 15, (500, 1000, 2000)),
    ("DR412i", "Hidráulico", "Mobil DTE 10 EXCEL 46", "LL-0004", 1500, (1000, 2000)),
    ("DR412i", "Cubos fan (total)", "MOBIL SHC RARUS 46", "LL-0003", 10, (1000, 2000)),
    ("DR412i", "Compresor", "MOBIL SHC RARUS 46", "LL-0003", 200, (1000, 2000)),
    ("DR412i", "Refrigerante", "MOBIL MINING COOLANT 50%", "LL-0007", 150, (2000,)),
]


def _config(repo: Repositorio):
    params = {k: v for k, _, v in PARAMS_DEF}
    params["usuario"] = "Usuario demo"
    repo.set_config("params", params, commit=False)
    repo.set_config("equipos", [{"equipo": e, "modelo": m, "faena": FAENA} for e, m in EQUIPOS], commit=False)
    repo.set_config("ciclos", CICLOS, commit=False)
    repo.set_config("tipos", TIPOS, commit=False)
    repo.set_config("aceites_cfg", [{"modelo": m, "componente": c, "frecuencia": f,
                                     "texto": f"Cambio cada {f} h"} for m, lst in ACEITES.items() for c, f in lst],
                    commit=False)
    repo.set_config("consumo_tipos", TIPOS_CONSUMO, commit=False)
    repo.set_config("consumo", [dict({"modelo": m, "sistema": s, "lubricante": lu, "parte": p, "litros": float(li)},
                                     **{str(t): (1.0 if t in usa else 0.0) for t in TIPOS_CONSUMO})
                                for m, s, lu, p, li, usa in CONSUMO], commit=False)
    repo.set_config("diario", [{"equipo": e, "parte": "LL-0006", "lubricante": "MOBIL ALMO 529",
                                "litros_dia": 20.0 if m == "DI650i" else 0.0} for e, m in EQUIPOS], commit=False)
    repo.set_config("precios", PRECIOS_DEFECTO, commit=False)
    kits, desc, n = [], [], 1000
    cuadros = [("DI650i", t, 1, "D10 - D11") for t in (250, 500, 1000, 1500)]
    cuadros += [("DR412i", 250, 1, "D14 - D15 - D16"), ("DR412i", 500, 1, "D14"), ("DR412i", 500, 2, "D15 - D16"),
                ("DR412i", 1000, 1, "D14 - D15 - D16"), ("DR412i", 2000, 1, "D14 - D15 - D16")]
    rng = random.Random(11)
    nombres = ["Filtro de aceite motor", "Filtro de combustible", "Filtro de aire primario", "Filtro hidráulico",
               "Filtro separador", "Filtro de aire secundario", "Junta tapa válvulas", "Correa alternador"]
    for i, (mod, tipo, cuadro, eqs) in enumerate(cuadros):
        kit = f"KIT-DEMO-{i + 1:02d}"
        items = 3 + tipo // 500
        base = dict(modelo=mod, tipo=float(tipo), cuadro=cuadro, kit=kit, ubic_kit=f"BOD-{i + 1}", equipos=eqs)
        kits.append(dict(base, linea=1, tipo_linea="SUB", np=f"KIT {kit}", cant=None, ubic="",
                         com=f"Contenido del kit ({items} ítems)"))
        for j in range(items):
            n += 1
            np_ = f"DEMO-{n}"
            kits.append(dict(base, linea=2 + j, tipo_linea="KIT", np=np_, cant=float(rng.choice((1, 1, 2))),
                             ubic=f"{rng.randint(1, 4)}{rng.choice('ABC')}{rng.randint(1, 6)}", com=""))
            desc.append({"np": np_, "descripcion": nombres[j % len(nombres)]})
        kits.append(dict(base, linea=2 + items, tipo_linea="SUB", np="ADICIONALES", cant=None, ubic="",
                         com="Repuestos adicionales (fuera del kit)"))
        n += 1
        kits.append(dict(base, linea=3 + items, tipo_linea="ADIC", np=f"DEMO-{n}", cant=2.0, ubic="BODFIL", com=""))
        desc.append({"np": f"DEMO-{n}", "descripcion": "Abrazadera de manguera"})
    repo.set_config("kits", kits, commit=False)
    repo.set_config("descripciones", desc, commit=False)


def _historial(repo: Repositorio, hoy: dt.date, rng: random.Random) -> dict:
    ult = {}
    pm_id = 0
    filas = []
    for eq, modelo in EQUIPOS:
        ciclo = next(c for c in CICLOS if c["modelo"] == modelo)
        seq = [ciclo[f"pos{k}"] for k in range(1, ciclo["largo"] + 1)]
        tasa = rng.uniform(9.5, 13.5)
        horo = rng.randint(6000, 11000)
        fecha = hoy - dt.timedelta(days=720 + rng.randint(0, 30))
        pos = rng.randint(0, ciclo["largo"] - 1)
        tipo = 250
        n = 0
        while True:
            delta = 250 + rng.choice((-30, -15, -8, 0, 5, 12, 20, 35, 60))
            dias = max(10, round(delta / (tasa * rng.uniform(0.85, 1.15))))
            nueva = fecha + dt.timedelta(days=dias)
            if nueva > hoy - dt.timedelta(days=rng.randint(2, 15)):
                break
            horo, fecha = horo + delta, nueva
            if n and tipo == 250:
                pos = pos % ciclo["largo"] + 1
                tipo = seq[pos - 1]
            elif n:
                tipo = 250
            filas.append((fecha, eq, modelo, tipo, horo))
            n += 1
        ult[eq] = (fecha, horo, tasa)
    filas.sort()
    previo = {}
    for fecha, eq, modelo, tipo, horo in filas:
        pm_id += 1
        fprog = fecha + dt.timedelta(days=rng.choice((-3, -2, -1, 0, 0, 0, 1, 2, 4))) \
            if (hoy - fecha).days < 240 else None
        obs = rng.choice([""] * 12 + ["Cambio de filtros adicional", "Se detecta fuga menor, corregida",
                                     "Ejecutada en turno noche"])
        repo.agregar_historial({
            "id": pm_id, "equipo": eq, "modelo": modelo, "faena": FAENA, "tipo": float(tipo), "fecha": fecha,
            "horo": float(horo), "horas": float(horo - previo[eq]) if eq in previo else None, "fprog": fprog,
            "obs": obs, "reg_el": dt.datetime.combine(fecha, dt.time(rng.randint(8, 20), rng.randint(0, 59))),
            "reg_por": rng.choice(["Turno A", "Turno B"]), "pos": None})
        previo[eq] = horo
        for comp, freq in ACEITES[modelo]:
            if tipo < freq and rng.random() > 0.02:
                continue
            r = rng.random()
            if r < 0.04:
                origen, h = ORIGEN_NO, None
            elif r < 0.08:
                origen, h = ORIGEN_FUERA, float(horo - rng.randint(5, 40))
            else:
                origen, h = ORIGEN_PM, float(horo)
            repo.agregar_aceite({"id_pm": pm_id, "equipo": eq, "comp": comp, "horo": h, "origen": origen,
                                 "reg_el": dt.datetime.combine(fecha, dt.time(21, 0)), "horas_ac": None})
    return ult


def crear_demo(repo: Repositorio, hoy: dt.date | None = None, semilla: int = 2026) -> dict:
    """Llena una base vacía con la flota de ejemplo. Devuelve un resumen."""
    from .acciones import Acciones
    from .motor import Motor

    hoy = hoy or dt.date.today()
    rng = random.Random(semilla)
    with repo.transaccion():
        repo.vaciar_todo()
        _config(repo)
        ult = _historial(repo, hoy, rng)
        for eq, (fecha, horo, tasa) in ult.items():
            repo.set_lectura(eq, float(round(horo + tasa * (hoy - fecha).days * rng.uniform(0.9, 1.05))), hoy,
                             "Usuario demo")
        repo.set_config("periodos", {"desde": hoy.replace(day=1).isoformat(),
                                     "hasta": (hoy + dt.timedelta(days=60)).isoformat(),
                                     "sem_ini": hoy.isoformat(), "sem_n": 4}, commit=False)
        repo.set_config("equipo_sel", EQUIPOS[0][0], commit=False)

    class _Mudo:
        def __getattr__(self, _):
            return lambda *a, **k: True

    m = Motor(repo, hoy=hoy)
    acc = Acciones(m, _Mudo())
    acc.reparar_claves(silencioso=True)
    acc.recalcular_horas_aceites(silencioso=True)
    m.recargar()
    with repo.transaccion():   # algunas PM programadas, otras no
        for eq in ("D10", "D14", "D16"):
            e = m.estado(eq)
            if e["n"]:
                f = max(hoy, e["fecha_sug"] - dt.timedelta(days=rng.randint(0, 2)))
                repo.set_programacion(eq, e["sugerido"], e["proyectado"], f, dt.datetime.now())
    m.recargar()
    return {"historial": len(m.hist), "aceites": len(m.ac), "plantillas": 0}
