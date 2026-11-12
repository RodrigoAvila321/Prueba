"""Compara el motor de Python con los valores que Excel dejó calculados en el libro original.

Uso:  python -m pytest tests  (requiere la variable PLANPM_XLSM con la ruta al .xlsm)
      o: python tests/test_equivalencia.py ruta/al/libro.xlsm
La fecha «hoy» se fija en la del último cálculo del libro (lecturas + días transcurridos).
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planificacion_pm.db import Repositorio  # noqa: E402
from planificacion_pm.importar import importar_libro  # noqa: E402
from planificacion_pm.motor import Motor  # noqa: E402

XLSM = os.environ.get("PLANPM_XLSM")


def _hoy_del_libro(wb) -> dt.date:
    """Horómetro estimado hoy = lectura + avance × días desde la lectura  ->  despeja los días."""
    c = wb["Calc"]
    lect, fl, prom = wb["Panel"]["I2"].value, wb["Panel"]["K2"].value, c["B47"].value
    dias = round((c["B42"].value - lect) / prom) if prom else 0
    return dt.date(fl.year, fl.month, fl.day) + dt.timedelta(days=dias)


def _cerca(a, b, tol=0.01):
    if isinstance(b, dt.datetime):
        b = b.date()
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol
    return a == b


def comparar(ruta: str) -> list[str]:
    wb = openpyxl.load_workbook(ruta, data_only=True)
    hoy = _hoy_del_libro(wb)
    tmp = tempfile.mkdtemp()
    repo = Repositorio(Path(tmp) / "t.db")
    importar_libro(ruta, repo)
    m = Motor(repo, hoy=hoy)
    errores: list[str] = []

    def chk(nombre, a, b):
        if not _cerca(a, b):
            errores.append(f"{nombre}: python={a!r} excel={b!r}")

    # ---- Calc (equipo seleccionado)
    eq = wb["Panel"]["C2"].value
    e = m.estado(eq)
    c = wb["Calc"]
    mapa = {2: "n", 4: "ult_tipo", 5: "ult_horo", 7: "n_mayor", 10: "largo", 11: "pos_last", 12: "pos_sig",
            13: "sig_mayor", 14: "sugerido", 15: "posterior", 17: "horo_hoy", 18: "proyectado", 19: "acum",
            20: "rest", 23: "promedio", 24: "fecha_proy", 26: "estado", 28: "fprog", 29: "horo_en_prog",
            30: "exceso", 31: "estado_prog", 32: "detalle_prog", 33: "horo_post", 34: "fecha_base",
            35: "fecha_post", 39: "dias_rest", 40: "margen_dias", 41: "fecha_sug", 42: "horo_est_hoy",
            45: "fecha_av_pm", 46: "horo_av_pm", 47: "promedio_proy", 48: "horo_est_hoy_real", 49: "horo_av_pm_real"}
    for fila, k in mapa.items():
        chk(f"Calc!{c.cell(fila, 3).value}", e[k], c.cell(fila, 2).value)
    chk("Panel!E9 cumplimiento", e["cumplimiento"], wb["Panel"]["E9"].value)
    chk("Panel!P2 alerta", e["alerta"], wb["Panel"]["P2"].value or "")

    # ---- Control de aceites del Panel
    for i, a in enumerate(m.control_aceites(eq)):
        r = 6 + i
        for col, k in (("N", "componente"), ("P", "ult"), ("Q", "acum"), ("R", "rest"), ("S", "estado")):
            chk(f"Panel!{col}{r}", a[k], wb["Panel"][f"{col}{r}"].value)

    # ---- CalcFlota: estado y proyección por equipo
    cf = wb["CalcFlota"]
    for i, eqx in enumerate(m.lista_equipos()):
        ex = m.estado(eqx)
        r = 4 + i
        for col, k in (("N", "sugerido"), ("Q", "proyectado"), ("U", "fecha_proy"), ("X", "fecha_base")):
            chk(f"CalcFlota!{col}{r}", ex[k], cf[f"{col}{r}"].value)
        chk(f"CalcFlota!T{r}", ex["promedio_proy"], cf[f"T{r}"].value)
        pr = m.proyeccion(eqx)
        for k in range(120):
            rr = 12 + i * 120 + k
            x = pr[k] if k < len(pr) else None
            if x is None:
                continue
            chk(f"CalcFlota!D{rr}", x["tipo"], cf[f"D{rr}"].value)
            chk(f"CalcFlota!F{rr}", x["fecha"], cf[f"F{rr}"].value)
            for j, pt in enumerate(["LL-0001", "LL-0002", "LL-0003", "LL-0004", "LL-0005", "LL-0007"]):
                chk(f"CalcFlota!{'HIJKLM'[j]}{rr}", x["litros"][pt], cf.cell(rr, 8 + j).value)

    # ---- Proyección aceites
    pa = wb["Proyección aceites"]
    d1, d2 = pa["D5"].value, pa["D6"].value
    per = m.periodo(d1.date() if d1 else None, d2.date() if d2 else None)
    for i, f in enumerate(per["filas"]):
        r = 11 + i
        chk(f"PA!B{r}", f["parte"], pa[f"B{r}"].value)
        for j, v in enumerate(f["por_eq"]):
            chk(f"PA!{'DEFGH'[j]}{r}", v, pa.cell(r, 4 + j).value)
        for col, k in (("I", "ejec"), ("J", "proy"), ("K", "total"), ("M", "con_margen"), ("N", "tarros"),
                       ("O", "sobrante")):
            chk(f"PA!{col}{r}", f[k], pa[f"{col}{r}"].value)
    for j, v in enumerate(per["n_pm"]):
        chk(f"PA!{'DEFGH'[j]}19", v, pa.cell(19, 4 + j).value)
    for i, a in enumerate(per["anos"]):
        r = 25 + i
        chk(f"PA!B{r}", a["ano"], pa[f"B{r}"].value)
        chk(f"PA!D{r}", a["n_ej"], pa[f"D{r}"].value)
        chk(f"PA!E{r}", a["n_pr"], pa[f"E{r}"].value)
        chk(f"PA!M{r}", a["total"], pa[f"M{r}"].value)

    # ---- Aceites por semanas
    sw = wb["Aceites por semanas"]
    s = m.semanas(sw["D5"].value.date(), sw["D6"].value)
    for i, f in enumerate(s["filas"]):
        r = 11 + i
        for j, v in enumerate(f["por_eq"]):
            chk(f"APS!{'DEFGH'[j]}{r}", v, sw.cell(r, 4 + j).value)
        chk(f"APS!K{r}", f["con_margen"], sw[f"K{r}"].value)
        chk(f"APS!L{r}", f["tarros"], sw[f"L{r}"].value)
    for j, v in enumerate(s["n_pm"]):
        chk(f"APS!{'DEFGH'[j]}19", v, sw.cell(19, 4 + j).value)
    for i, w in enumerate(s["semanas"]):
        r = 25 + i
        chk(f"APS!C{r}", w["periodo"], sw[f"C{r}"].value)
        chk(f"APS!D{r}", w["iso"], sw[f"D{r}"].value)
        for j, txt in enumerate(w["celdas"]):
            chk(f"APS!{'EFGHI'[j]}{r}", txt, sw.cell(r, 5 + j).value)
        chk(f"APS!J{r}", w["n_pm"], sw[f"J{r}"].value)
        chk(f"APS!R{r}", w["total"], sw[f"R{r}"].value)

    # ---- Kits a solicitar
    ks = wb["Kits a solicitar"]
    k = m.kits_solicitar(per, s)
    for i, f in enumerate(k["kits"]):
        r = 20 + i
        chk(f"KS!B{r}", f["kit"], ks[f"B{r}"].value)
        chk(f"KS!L{r}", f["n_per"], ks[f"L{r}"].value)
        chk(f"KS!M{r}", f["n_sem"], ks[f"M{r}"].value)
    rep = {x["np"]: x for x in k["repuestos"]}
    r = 33
    while ks[f"B{r}"].value and not str(ks[f"B{r}"].value).startswith(("TOTAL", "Lista")):
        np_ = str(ks[f"B{r}"].value)
        if np_ in rep:
            chk(f"KS!L{r}", rep[np_]["n_per"], ks[f"L{r}"].value)
            chk(f"KS!M{r}", rep[np_]["n_sem"], ks[f"M{r}"].value)
        else:
            errores.append(f"KS!B{r}: repuesto {np_} no encontrado")
        r += 1
    repo.cerrar()
    return errores


@pytest.mark.skipif(not XLSM, reason="Defina PLANPM_XLSM con la ruta al libro original")
def test_equivalencia():
    err = comparar(XLSM)
    assert not err, "\n".join(err[:50])


if __name__ == "__main__":
    errs = comparar(sys.argv[1])
    print("\n".join(errs[:80]))
    print(f"{len(errs)} diferencias")
