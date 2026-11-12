"""Exportaciones a Excel (.xlsx): ExportarCompra, ExportarSemanas, ExportarListado y
ExportarSolicitudAnalisis del libro original."""
from __future__ import annotations

import datetime as dt
import io
from collections import OrderedDict

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .motor import Motor, categoria_suelto
from .util import ORIGEN_FUERA, ORIGEN_NO, ORIGEN_PM, es_num, fmt_fecha, fmt_pct, fmt_tipo

AZUL = "1F3864"
GRIS = "595959"
FMT_N = "#,##0"
FMT_GUION = '#,##0;-#,##0;"-"'
FMT_F = "dd-mm-yyyy"
FLOTA = "FLOTA"


def _flota(m: Motor) -> str:
    return " · ".join(m.lista_equipos())


def _libro():
    wb = openpyxl.Workbook()
    return wb, wb.active


def _hoja(wb, nombre):
    return wb.create_sheet(nombre)


def _fuente_base(ws, filas: int, cols: int):
    f = Font(name="Arial", size=10)
    for r in ws.iter_rows(min_row=1, max_row=filas, max_col=cols):
        for c in r:
            if c.font == Font() or c.font.name == "Calibri":
                c.font = f


def _titulo(ws, celda: str, texto: str, tam=14):
    ws[celda] = texto
    ws[celda].font = Font(name="Arial", size=tam, bold=True, color=AZUL)


def _nota(ws, celda: str, texto: str, cursiva=False, color=GRIS):
    ws[celda] = texto
    ws[celda].font = Font(name="Arial", size=10, italic=cursiva, color=color)


def formato_tabla(ws, r1: int, c1: int, r2: int, c2: int, filas_total: int = 1):
    """FormatoTabla de VBA: encabezado azul, bordes y fila de total destacada."""
    lado = Side(style="thin", color="BFBFBF")
    borde = Border(left=lado, right=lado, top=lado, bottom=lado)
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            cel = ws.cell(r, c)
            cel.border = borde
            h = "center" if c >= c1 + 2 and r > r1 else cel.alignment.horizontal
            cel.alignment = Alignment(vertical="center", horizontal=h, wrap_text=cel.alignment.wrap_text)
            if cel.font.name != "Arial":
                cel.font = Font(name="Arial", size=10)
    for c in range(c1, c2 + 1):
        cel = ws.cell(r1, c)
        cel.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor=AZUL)
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[r1].height = 30
    for r in range(r2 - filas_total + 1, r2 + 1):
        for c in range(c1, c2 + 1):
            cel = ws.cell(r, c)
            cel.font = Font(name="Arial", size=10, bold=True, color=AZUL)
            cel.fill = PatternFill("solid", fgColor="DDEBF7")


def _anchos(ws, anchos: dict):
    for col, w in anchos.items():
        ws.column_dimensions[col].width = w


def _formato_num(ws, r1, c1, r2, c2, fmt):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(r, c).number_format = fmt


def _destacar_tarros(ws, r1, r2, col):
    for r in range(r1, r2 + 1):
        c = ws.cell(r, col)
        c.fill = PatternFill("solid", fgColor="FCE4D6")
        c.font = Font(name="Arial", size=10, bold=True, color="C55A11")


def _cabecera(ws, d1, d2, titulo, linea3, m: Motor, usuario: str, origen: str, extra=""):
    _titulo(ws, "A1", titulo)
    _nota(ws, "A2", extra or f"Período: {fmt_fecha(d1)} al {fmt_fecha(d2)} ({(d2 - d1).days + 1} días)")
    _nota(ws, "A3", linea3)
    _nota(ws, "A4", f"Margen de seguridad: {fmt_pct(m.p['margen'])}  ·  Tarro: {fmt_tipo(m.p['tarro'])} L")
    _nota(ws, "A5", f"Exportado el {dt.datetime.now():%d-%m-%Y %H:%M} por {usuario}  ·  Origen: {origen}")


# =========================================================================== kits
def escribir_kits(ws, m: Motor, ks: dict, campo: str, titulo: str, criterio: str = ""):
    _titulo(ws, "A1", titulo, 13)
    _nota(ws, "A2", (criterio or "Solo PM proyectadas desde hoy.") +
          " Un kit por PM (DR412i PM 500: BG00954918 para D14 y BG01171477 para D15 - D16). "
          "Repuestos sueltos = cantidad por PM × N° de PM.", cursiva=True)
    r0 = 4
    for j, h in enumerate(["N° de kit", "Modelo · PM", "Equipos", "Ubicación", "Cantidad"]):
        ws.cell(r0, 1 + j, h)
    r, tot = r0, 0.0
    for k in ks["kits"]:
        if k[campo] > 0:
            r += 1
            for j, v in enumerate([k["kit"], k["etiqueta"], k["equipos"], k["ubic"], k[campo]]):
                ws.cell(r, 1 + j, v)
            tot += k[campo]
    if r == r0:
        r += 1
        ws.cell(r, 1, "Sin PM proyectadas en este período.")
    r += 1
    ws.cell(r, 1, "TOTAL KITS")
    ws.cell(r, 5, tot)
    formato_tabla(ws, r0, 1, r, 5)
    for rr in range(r0 + 1, r + 1):
        ws.cell(rr, 3).alignment = Alignment(horizontal="left", vertical="center")
    r0 = r + 3
    ws.cell(r0 - 1, 1, "REPUESTOS SUELTOS (adicionales, pedir por separado y tomar de bodega)").font = \
        Font(name="Arial", size=10, bold=True, color=AZUL)
    for j, h in enumerate(["N° de parte", "Ubicación", "Origen", "Cantidad"]):
        ws.cell(r0, 1 + j, h)
    r, tot, n = r0, 0.0, 0
    for x in ks["repuestos"]:
        if x[campo] > 0:
            r += 1
            n += 1
            c = ws.cell(r, 1, str(x["np"]))
            c.number_format = "@"
            ws.cell(r, 2, x["ubic"])
            ws.cell(r, 3, x["origen"])
            ws.cell(r, 4, x[campo])
            tot += x[campo]
    if n == 0:
        r += 1
        ws.cell(r, 1, "Sin repuestos sueltos en este período.")
    r += 1
    ws.cell(r, 1, "TOTAL UNIDADES")
    ws.cell(r, 4, tot)
    formato_tabla(ws, r0, 1, r, 4)
    for rr in range(r0 + 1, r + 1):
        ws.cell(rr, 3).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    _anchos(ws, {"A": 16, "B": 18, "C": 70, "D": 14, "E": 14})


# ================================================================ compra de aceites
def exportar_compra(m: Motor, d1: dt.date, d2: dt.date, ruta: str, usuario: str, origen: str) -> dict:
    per = m.periodo(d1, d2)
    tarro, margen = float(m.p["tarro"]), float(m.p["margen"])
    fin_ej = min(d2, m.hoy)
    wb, ws1 = _libro()
    ws1.title = "Resumen"
    ws2 = _hoja(wb, "Por equipo")
    ws4 = _hoja(wb, "Mes a mes")
    ws3 = _hoja(wb, "PM incluidas")

    # ---- Resumen
    _cabecera(ws1, d1, d2, f"COMPRA DE ACEITES · FLOTA {_flota(m)}", m.texto_tramos(d1, d2), m, usuario, origen)
    hdr = ["N° parte", "Lubricante", "Ejecutado (L)", "Proyectado (L)", "Total período (L)",
           f"Margen {fmt_pct(margen)} (L)", "Total con margen (L)", f"Tarros ({fmt_tipo(tarro)} L)", "Litros sobrantes"]
    for j, h in enumerate(hdr):
        ws1.cell(7, 1 + j, h)
    for i, f in enumerate(per["filas"]):
        r = 8 + i
        for j, v in enumerate([f["parte"], f["nombre"], f["ejec"], f["proy"], f["total"], f["margen"],
                               f["con_margen"], f["tarros"], f["sobrante"]]):
            ws1.cell(r, 1 + j, v)
    r = 8 + len(per["filas"])
    ws1.cell(r, 1, "TOTAL")
    for j in range(3, 10):
        ws1.cell(r, j, sum(ws1.cell(k, j).value or 0 for k in range(8, r)))
    ws1.cell(r + 2, 1, f"PM ejecutadas en el período: {per['n_ej_total']}  ·  PM proyectadas: {per['n_pr_total']}"
                       f"  ·  Total: {per['n_ej_total'] + per['n_pr_total']}")
    formato_tabla(ws1, 7, 1, r, 9, 2)
    _formato_num(ws1, 8, 3, r, 9, FMT_N)
    _destacar_tarros(ws1, 8, r, 8)
    _anchos(ws1, {"A": 12, "B": 32, **{get_column_letter(c): 15 for c in range(3, 10)}})

    # ---- Por equipo
    eqs = per["equipos"]
    _titulo(ws2, "A1", f"LITROS POR EQUIPO (sin margen) · {fmt_fecha(d1)} al {fmt_fecha(d2)}", 13)
    ws2.cell(3, 1, "N° parte")
    ws2.cell(3, 2, "Lubricante")
    for j, eq in enumerate(eqs):
        ws2.cell(3, 3 + j, eq)
    ct = 3 + len(eqs)
    ws2.cell(3, ct, "Total período (L)")
    for i, f in enumerate(per["filas"]):
        r = 4 + i
        ws2.cell(r, 1, f["parte"])
        ws2.cell(r, 2, f["nombre"])
        for j, v in enumerate(f["por_eq"]):
            ws2.cell(r, 3 + j, v)
        ws2.cell(r, ct, f["total"])
    r = 4 + len(per["filas"])
    ws2.cell(r, 1, "TOTAL")
    for j in range(3, ct + 1):
        ws2.cell(r, j, sum(ws2.cell(k, j).value or 0 for k in range(4, r)))
    ws2.cell(r + 1, 2, "N° de PM")
    for j, v in enumerate(per["n_pm"]):
        ws2.cell(r + 1, 3 + j, v)
    ws2.cell(r + 1, ct, sum(per["n_pm"]))
    formato_tabla(ws2, 3, 1, r + 1, ct, 2)
    _formato_num(ws2, 4, 3, r + 1, ct, FMT_N)
    _anchos(ws2, {"A": 12, "B": 32, **{get_column_letter(c): 14 for c in range(3, ct + 1)}})

    # ---- PM incluidas (lubricantes que dependen de las PM)
    pm_partes = [f["parte"] for f in per["filas"] if f["parte"] in m.partes_pm()]
    diarias = [f for f in per["filas"] if f["parte"] not in pm_partes and m.tasa_diaria(f["parte"]) > 0]
    filas = []
    for h in m.hist:
        eq = h["equipo"].strip()
        if eq and h["fecha"] and d1 <= h["fecha"] <= fin_ej:
            modelo = m.modelo_de(eq)
            lit = [m.litros_pm(modelo, h["tipo"], pt) for pt in pm_partes]
            filas.append([h["equipo"], modelo, h["tipo"], h["fecha"], h["horo"], "Ejecutada", *lit, sum(lit)])
    for x in m.proyeccion_flota():
        if d1 <= x["fecha"] <= d2:
            lit = [x["litros"].get(pt, 0.0) for pt in pm_partes]
            filas.append([x["equipo"], x["modelo"], x["tipo"], x["fecha"], x["horo"], "Proyectada", *lit, sum(lit)])
    filas.sort(key=lambda f: (f[3], str(f[0])))
    nP = len(pm_partes)
    for j, h in enumerate(["Equipo", "Modelo", "Tipo PM", "Fecha", "Horómetro", "Estado"]
                          + [f"{pt} (L)" for pt in pm_partes] + ["Total (L)"]):
        ws3.cell(1, 1 + j, h)
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            ws3.cell(2 + i, 1 + j, v)
    r = len(filas) + 2
    ws3.cell(r, 1, f"TOTAL ({len(filas)} PM)")
    for j in range(7, 8 + nP):
        ws3.cell(r, j, sum(ws3.cell(k, j).value or 0 for k in range(2, r)))
    formato_tabla(ws3, 1, 1, r, 7 + nP)
    _formato_num(ws3, 2, 4, r, 4, FMT_F)
    _formato_num(ws3, 2, 5, r, 5, FMT_N)
    _formato_num(ws3, 2, 7, r, 7 + nP, FMT_GUION)
    _anchos(ws3, {get_column_letter(c): 12 for c in range(1, 8 + nP)})
    suma_l = ws3.cell(r, 7 + nP).value or 0
    if diarias:
        _nota(ws3, f"A{r + 2}", "Consumo diario no asociado a PM (incluido en Resumen, Por equipo y Mes a mes): "
              + "; ".join(f"{f['parte']} {f['nombre']}" for f in diarias) + ".", cursiva=True, color="000000")
    suma_hoja = sum(f["total"] for f in per["filas"] if f["parte"] in pm_partes)
    aviso = ""
    if abs(suma_l - suma_hoja) > 0.5:
        aviso = (f"Atención: la suma de la lista de PM ({suma_l:,.0f} L) no coincide con el total del período "
                 f"({suma_hoja:,.0f} L). Revise PM sin modelo o tipos fuera de la cartilla.")
        _nota(ws3, f"A{r + 3}", aviso, color="C00000")

    # ---- Mes a mes
    partes = per["partes"]
    nL = len(partes)
    primero = d1.replace(day=1)
    nM = (d2.year - d1.year) * 12 + d2.month - d1.month + 1
    _titulo(ws4, "A1", f"DETALLE MES A MES (litros sin margen) · {fmt_fecha(d1)} al {fmt_fecha(d2)}", 13)
    ws4.cell(3, 1, "Mes")
    ws4.cell(3, 2, "PM ejecutadas")
    ws4.cell(3, 3, "PM proyectadas")
    for j, f in enumerate(per["filas"]):
        ws4.cell(3, 4 + j, f"{f['parte']}\n{f['nombre']}")
    ws4.cell(3, 4 + nL, "Total litros")
    for i in range(nM):
        mi = dt.date(primero.year + (primero.month - 1 + i) // 12, (primero.month - 1 + i) % 12 + 1, 1)
        mf = (dt.date(mi.year + mi.month // 12, mi.month % 12 + 1, 1) - dt.timedelta(days=1))
        a, b = max(mi, d1), min(mf, d2)
        de_mes = [f for f in filas if a <= f[3] <= b]
        r = 4 + i
        ws4.cell(r, 1, mi)
        ws4.cell(r, 2, sum(1 for f in de_mes if f[5] == "Ejecutada"))
        ws4.cell(r, 3, sum(1 for f in de_mes if f[5] != "Ejecutada"))
        tot = 0.0
        for j, pt in enumerate(partes):
            if pt in pm_partes:
                k = pm_partes.index(pt)
                v = sum(f[6 + k] for f in de_mes)
            else:
                v = ((b - a).days + 1) * m.tasa_diaria(pt)
            ws4.cell(r, 4 + j, v)
            tot += v
        ws4.cell(r, 4 + nL, tot)
    r = 4 + nM
    ws4.cell(r, 1, "TOTAL")
    for j in range(2, 5 + nL):
        ws4.cell(r, j, sum(ws4.cell(k, j).value or 0 for k in range(4, r)))
    formato_tabla(ws4, 3, 1, r, 4 + nL)
    ws4.row_dimensions[3].height = 42
    _formato_num(ws4, 4, 1, r - 1, 1, "mmmm yyyy")
    for k in range(4, r + 1):
        ws4.cell(k, 1).alignment = Alignment(horizontal="left", vertical="center")
    _formato_num(ws4, 4, 2, r, 4 + nL, FMT_GUION)
    _anchos(ws4, {"A": 16, "B": 11, "C": 11, **{get_column_letter(c): 14 for c in range(4, 5 + nL)}})
    _nota(ws4, f"A{r + 2}", "Meses parciales: solo se cuentan los días dentro del período. El consumo diario usa "
          "los litros por día de la Configuración.", cursiva=True, color="000000")

    # ---- Kits a solicitar
    sem_cfg = m.repo.get_config("periodos", {})
    sem = m.semanas(_f(sem_cfg.get("sem_ini")), sem_cfg.get("sem_n") or 4)
    ks = m.kits_solicitar(per, sem)
    escribir_kits(_hoja(wb, "Kits a solicitar"), m, ks, "n_per",
                  f"KITS A SOLICITAR · PERÍODO {fmt_fecha(d1)} al {fmt_fecha(d2)}")
    wb.active = 0
    wb.save(ruta)
    return dict(per=per, n_pm=len(filas), aviso=aviso)


def _f(s):
    try:
        return dt.date.fromisoformat(s) if s else None
    except ValueError:
        return None


# ================================================================ aceites por semanas
def exportar_semanas(m: Motor, ini: dt.date, n: int, ruta: str, usuario: str, origen: str) -> dict:
    s = m.semanas(ini, n)
    d1, d2, n = s["ini"], s["fin"], s["n"]
    tarro, margen = float(m.p["tarro"]), float(m.p["margen"])
    eqs, partes = s["equipos"], s["partes"]
    nE, nL = len(eqs), len(partes)
    wb, ws1 = _libro()
    ws1.title = "Resumen"
    ws2 = _hoja(wb, "Semana a semana")
    ws3 = _hoja(wb, "PM incluidas")
    diarias = [pt for pt in partes if m.tasa_diaria(pt) > 0 and pt not in m.partes_pm()]
    sem_txt = f"{n} {'semana' if n == 1 else 'semanas'}"
    _cabecera(ws1, d1, d2, f"ACEITES POR SEMANAS · FLOTA {_flota(m)}",
              ("PM ejecutadas (Historial) hasta hoy + PM proyectadas desde hoy" if d1 <= m.hoy else "PM proyectadas")
              + (". " + ", ".join(f"{pt} {m.nombre_parte(pt).replace(' (consumo diario)', '')}" for pt in diarias)
                 + " suma su consumo diario por cada día del plazo." if diarias else "."),
              m, usuario, origen, extra=f"Plazo: {fmt_fecha(d1)} al {fmt_fecha(d2)} ({sem_txt}, {7 * n} días)")
    hdr = ["N° parte", "Lubricante", *eqs, "Total plazo (L)", f"Margen {fmt_pct(margen)} (L)", "Total con margen (L)",
           f"Tarros ({fmt_tipo(tarro)} L)", "Litros sobrantes"]
    for j, h in enumerate(hdr):
        ws1.cell(7, 1 + j, h)
    for i, f in enumerate(s["filas"]):
        r = 8 + i
        vals = [f["parte"], f["nombre"], *f["por_eq"], f["total"], f["margen"], f["con_margen"], f["tarros"],
                f["sobrante"]]
        for j, v in enumerate(vals):
            ws1.cell(r, 1 + j, v)
    r = 8 + nL
    nc = len(hdr)
    ws1.cell(r, 1, "TOTAL")
    for j in range(3, nc + 1):
        ws1.cell(r, j, sum(ws1.cell(k, j).value or 0 for k in range(8, r)))
    ws1.cell(r + 1, 2, "N° de PM proyectadas")
    for j, v in enumerate(s["n_pm"]):
        ws1.cell(r + 1, 3 + j, v)
    ws1.cell(r + 1, 3 + nE, s["n_pm_total"])
    formato_tabla(ws1, 7, 1, r + 1, nc, 2)
    _formato_num(ws1, 8, 3, r + 1, nc, FMT_N)
    _destacar_tarros(ws1, 8, r, nc - 1)
    _anchos(ws1, {"A": 12, "B": 32, **{get_column_letter(c): 14 for c in range(3, nc + 1)}})

    # ---- Semana a semana
    _titulo(ws2, "A1", f"SEMANA A SEMANA (litros sin margen) · {fmt_fecha(d1)} al {fmt_fecha(d2)}", 13)
    _nota(ws2, "A2", "Columnas de equipos: PM del equipo en la semana (tipo · fecha); «(ejec.)» = registrada en el "
          "Historial; «(+1)» indica una segunda PM en la misma semana.", cursiva=True)
    hdr = ["Semana", "Período", "Sem. ISO", *eqs, "N° PM", *partes, "Total (L)"]
    for j, h in enumerate(hdr):
        ws2.cell(4, 1 + j, h)
    for i, w in enumerate(s["semanas"]):
        vals = [w["sem"], w["periodo"], w["iso"], *w["celdas"], w["n_pm"], *[w["litros"][pt] for pt in partes],
                w["total"]]
        for j, v in enumerate(vals):
            ws2.cell(5 + i, 1 + j, v)
    r = 5 + n
    ws2.cell(r, 1, "TOTAL")
    for j, v in enumerate(s["n_pm"]):
        ws2.cell(r, 4 + j, f"{v} PM")
    c_npm = 4 + nE
    for j in range(c_npm, len(hdr) + 1):
        ws2.cell(r, j, sum(ws2.cell(k, j).value or 0 for k in range(5, r)))
    formato_tabla(ws2, 4, 1, r, len(hdr))
    ws2.row_dimensions[4].height = 42
    _formato_num(ws2, 5, c_npm + 1, r, len(hdr), FMT_GUION)
    for k in range(5, r + 1):
        ws2.cell(k, 2).alignment = Alignment(horizontal="left", vertical="center")
    _anchos(ws2, {"A": 9, "B": 22, "C": 10, **{get_column_letter(c): 17 for c in range(4, c_npm)},
                  **{get_column_letter(c): 13 for c in range(c_npm, len(hdr) + 1)}})

    # ---- PM incluidas
    pm_partes = m.partes_pm()
    nP = len(pm_partes)
    fin_ej = min(d2, m.hoy)
    filas = []
    for h in m.hist:
        if h["equipo"].strip() and h["fecha"] and d1 <= h["fecha"] <= fin_ej:
            nw = (h["fecha"] - d1).days // 7 + 1
            lit = [m.litros_pm(h["modelo"], h["tipo"], pt) for pt in pm_partes]
            filas.append([nw, s["semanas"][nw - 1]["iso"], "Ejecutada", h["equipo"], h["modelo"], h["tipo"],
                          h["fecha"], h["horo"], *lit, sum(lit)])
    for x in s["proyectadas"]:
        lit = [x["litros"].get(pt, 0.0) for pt in pm_partes]
        filas.append([x["sem"], s["semanas"][x["sem"] - 1]["iso"], "Proyectada", x["equipo"], x["modelo"], x["tipo"],
                      x["fecha"], x["horo"], *lit, sum(lit)])
    filas.sort(key=lambda f: (f[6], str(f[3])))
    _titulo(ws3, "A1", f"PM DEL PLAZO (ejecutadas hasta hoy + proyectadas) · {fmt_fecha(d1)} al {fmt_fecha(d2)}", 13)
    for j, h in enumerate(["Semana", "Sem. ISO", "Estado", "Equipo", "Modelo", "Tipo PM", "Fecha", "Horómetro"]
                          + [f"{pt} (L)" for pt in pm_partes] + ["Total (L)"]):
        ws3.cell(3, 1 + j, h)
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            ws3.cell(4 + i, 1 + j, v)
    r = len(filas) + 4
    ws3.cell(r, 1, f"TOTAL ({len(filas)} PM)")
    for j in range(9, 10 + nP):
        ws3.cell(r, j, sum(ws3.cell(k, j).value or 0 for k in range(4, r)))
    formato_tabla(ws3, 3, 1, r, 9 + nP)
    _formato_num(ws3, 4, 7, r, 7, FMT_F)
    _formato_num(ws3, 4, 8, r, 8, FMT_N)
    _formato_num(ws3, 4, 9, r, 9 + nP, FMT_GUION)
    _anchos(ws3, {get_column_letter(c): 12 for c in range(1, 10 + nP)})
    if diarias:
        _nota(ws3, f"A{r + 2}", "Consumo diario no asociado a PM (incluido en Resumen y Semana a semana): "
              + "; ".join(f"{pt} {m.nombre_parte(pt).replace('(consumo diario)', '').strip()}" for pt in diarias) + ".",
              cursiva=True, color="000000")
    suma_pm = ws3.cell(r, 9 + nP).value or 0
    tot_hoja = sum(f["total"] for f in s["filas"] if f["parte"] in pm_partes)
    aviso = ""
    if abs(suma_pm - tot_hoja) > 0.5:
        aviso = (f"Atención: la suma de la lista de PM ({suma_pm:,.0f} L) no coincide con el total del plazo sin "
                 f"consumo diario ({tot_hoja:,.0f} L). Revise la cartilla de consumo en Configuración.")
        _nota(ws3, f"A{r + 3}", aviso, color="C00000")

    # ---- Kits a solicitar
    per_cfg = m.repo.get_config("periodos", {})
    per = m.periodo(_f(per_cfg.get("desde")), _f(per_cfg.get("hasta")))
    ks = m.kits_solicitar(per, s)
    escribir_kits(_hoja(wb, "Kits a solicitar"), m, ks, "n_sem",
                  f"KITS A SOLICITAR · PLAZO {fmt_fecha(d1)} al {fmt_fecha(d2)} ({sem_txt})",
                  "PM ejecutadas (Historial) hasta hoy + PM proyectadas desde hoy.")
    wb.active = 0
    wb.save(ruta)
    return dict(sem=s, n_pm=len(filas), aviso=aviso)


# ======================================================= listado de repuestos (Kits PM)
def exportar_listado(m: Motor, ruta: str, origen: str) -> dict:
    cuadros = m.cuadros_kit()
    if not cuadros:
        raise ValueError("La tabla «Kits PM» no tiene kits.")
    cols = list(cuadros.values())
    mt: dict = {}
    for c in cols:
        mt[(c["modelo"], c["tipo"])] = mt.get((c["modelo"], c["tipo"]), 0) + 1
    hdr_s, hdr_c = [], []
    for c in cols:
        s = f"PM {fmt_tipo(c['tipo'])}"
        if mt[(c["modelo"], c["tipo"])] > 1:
            s += f" ({c['equipos_limpio']})"
        hdr_s.append(s)
        hdr_c.append(f"{c['modelo']} {s}")
    rep: OrderedDict = OrderedDict()
    cat = "suelto"
    for ci, c in enumerate(cols):
        for ln in c["lineas"]:
            tl = ln["tipo_linea"]
            if tl == "SUB":
                cat = "kit" if ln["linea"] == 1 else categoria_suelto(ln["com"])
            elif tl in ("KIT", "ADIC") and ln["np"]:
                r = rep.setdefault(ln["np"], dict(q=[0.0] * len(cols), rol=[[] for _ in cols], ub=[]))
                if es_num(ln["cant"]):
                    r["q"][ci] += float(ln["cant"])
                rol = "kit" if tl == "KIT" else cat
                if rol not in r["rol"][ci]:
                    r["rol"][ci].append(rol)
                u = (ln["ubic"] or "").strip()
                if u and u != "-" and u not in r["ub"]:
                    r["ub"].append(u)
    orden = sorted(rep)
    wb, ws = _libro()
    ws.title = "Listado"
    _titulo(ws, "A1", "LISTADO DE REPUESTOS Y KITS SIN DUPLICADOS · KITS PM")
    _nota(ws, "A2", f"Generado el {dt.datetime.now():%d-%m-%Y %H:%M} desde «Kits PM» de {origen}. Cantidad por PM = "
          "unidades que usa una PM de ese tipo (caja del kit + repuestos sueltos).")
    _nota(ws, "A3", f"{len(cols)} kits · {len(orden)} repuestos")
    for j, h in enumerate(["N° de parte", "Tipo", "Descripción", "Ubicación", "Dónde se usa", *hdr_c]):
        ws.cell(5, 1 + j, h)
    r = 5
    for ci, c in enumerate(cols):
        r += 1
        ws.cell(r, 1, c["kit"]).number_format = "@"
        ws.cell(r, 2, "Kit")
        ws.cell(r, 3, f"Kit {hdr_c[ci]}")
        ws.cell(r, 4, c["ubic_kit"])
        ws.cell(r, 5, f"{hdr_c[ci]} · equipos {c['equipos_limpio']}")
        ws.cell(r, 6 + ci, 1)
        for cc in range(1, 6 + len(cols)):
            ws.cell(r, cc).fill = PatternFill("solid", fgColor="DDEBF7")
    for np_ in orden:
        x = rep[np_]
        r += 1
        ub = list(x["ub"])
        if "SIN UBIC." in ub and len(ub) > 1:
            ub.remove("SIN UBIC.")
        modelos: OrderedDict = OrderedDict()
        for ci, c in enumerate(cols):
            if x["rol"][ci]:
                t = f"{hdr_s[ci]} ({' + '.join(x['rol'][ci])})"
                modelos[c["modelo"]] = (modelos[c["modelo"]] + ", " + t) if c["modelo"] in modelos else t
        ws.cell(r, 1, np_).number_format = "@"
        ws.cell(r, 2, "Repuesto")
        if np_ in m.descripciones:
            ws.cell(r, 3, m.descripciones[np_])
        ws.cell(r, 4, " / ".join(ub))
        ws.cell(r, 5, "; ".join(f"{k}: {v}" for k, v in modelos.items()))
        for ci, q in enumerate(x["q"]):
            if q:
                ws.cell(r, 6 + ci, q)
    nc = 5 + len(cols)
    lado = Side(style="thin", color="BFBFBF")
    for rr in range(5, r + 1):
        for cc in range(1, nc + 1):
            cel = ws.cell(rr, cc)
            cel.border = Border(left=lado, right=lado, top=lado, bottom=lado)
            h = "center" if cc in (1, 2, 4) or cc >= 6 else None
            cel.alignment = Alignment(vertical="center", horizontal=h, wrap_text=(cc == 5 or rr == 5))
            cel.font = Font(name="Arial", size=10, bold=(cc == 1 and rr > 5))
    for cc in range(1, nc + 1):
        cel = ws.cell(5, cc)
        cel.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor=AZUL)
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[5].height = 32
    _anchos(ws, {"A": 14, "B": 10, "C": 36, "D": 16, "E": 70,
                 **{get_column_letter(c): 11 for c in range(6, nc + 1)}})
    ws.auto_filter.ref = f"A5:{get_column_letter(nc)}{r}"
    ws.freeze_panes = "B6"
    wb.save(ruta)
    return dict(n_kits=len(cols), n_rep=len(orden))


# ======================================================== solicitud de análisis
def exportar_solicitud(m: Motor, eq: str, ruta: str) -> dict:
    modelo = m.modelo_de(eq)
    datos = m.repo.plantilla(modelo)
    if not datos:
        raise ValueError(f"No se encontró el formato de la solicitud para el modelo «{modelo}». "
                         "Impórtelo desde Configuración > Importar formato.")
    filas = m.hist_eq.get(eq, [])
    if not filas:
        raise ValueError(f"El equipo {eq} no tiene PM ejecutadas en el Historial.")
    ult = max(filas, key=lambda f: f["id"])
    id_pm, tipo, fecha, horo = ult["id"], ult["tipo"], ult["fecha"], float(ult["horo"] or 0)
    hoy = m.hoy
    wb = openpyxl.load_workbook(io.BytesIO(datos))
    ws = wb.worksheets[0]
    ws.title = f"Solicitud {eq}"[:31]
    n_si = n_filas = 0
    r = 7
    while str(ws.cell(r, 6).value or "").strip():
        comp = str(ws.cell(r, 16).value or "").strip()
        encontrado, origen, horas_pm, u = False, "", None, 0.0
        for a in m.ac:
            if a["equipo"].strip() == eq and (a["comp"] or "").strip().lower() == comp.lower():
                if a["id_pm"] == id_pm:
                    encontrado, origen, horas_pm = True, a["origen"], a["horas_ac"]
                if a["origen"] != ORIGEN_NO and es_num(a["horo"]) and u < a["horo"] <= horo:
                    u = float(a["horo"])
        if encontrado and origen in (ORIGEN_PM, ORIGEN_FUERA):
            n_si += 1
            ws.cell(r, 7, "SI")
            horas = horas_pm if horas_pm not in (None, "") else ("Sin registro" if u > 0 else "Sin cambio anterior")
        else:
            ws.cell(r, 7, "NO")
            horas = horo - u if u > 0 else "Sin registro"
        ws.cell(r, 5, eq)
        ws.cell(r, 8, horo)
        ws.cell(r, 9, horas)
        ws.cell(r, 10, horas)
        ws.cell(r, 11, hoy)
        for c in (8, 9, 10):
            ws.cell(r, c).number_format = FMT_N
        ws.cell(r, 11).number_format = FMT_F
        n_filas += 1
        r += 1
    for rr in range(1, ws.max_row + 1):
        ws.cell(rr, 16).value = None
    ws.column_dimensions["P"].hidden = True
    for rr in range(1, 81):
        b = str(ws.cell(rr, 2).value or "")
        if "cantidad de muestras" in b.lower():
            ws.cell(rr, 4, n_si)
        if "fecha de env" in b.lower():
            ws.cell(rr, 4, hoy).number_format = FMT_F
        if "comentarios generales" in str(ws.cell(rr, 7).value or "").lower():
            c = ws.cell(rr + 1, 7, f"PM {fmt_tipo(tipo)} ejecutada el {fmt_fecha(fecha)} · horómetro "
                                   f"{horo:,.0f} h".replace(",", "."))
            c.alignment = Alignment(horizontal="left", vertical=c.alignment.vertical, wrap_text=c.alignment.wrap_text)
    wb.save(ruta)
    return dict(tipo=tipo, fecha=fecha, horo=horo, n_si=n_si, n_filas=n_filas)
