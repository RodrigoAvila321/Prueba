"""Reporte PDF «Horas para la PM programada» de los equipos elegidos."""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .motor import Motor
from .resumen_pdf import (ANCHO, BORDE, CLARO, EST, GRIS, NAVY, NAVY2, ROJO, SUAVE, TEXTO, VERDE,
                          _chip, _p, _seccion, _tabla, marco_pagina)
from .util import fmt_fecha, fmt_num, fmt_tipo

AMBAR = colors.HexColor("#E0A100")
COLOR_ESTADO = {"Vencida": ROJO, "Próxima": AMBAR, "En plazo": VERDE}
CLARO[AMBAR] = colors.HexColor("#FFF1CC")


class BarraAvance(Flowable):
    """Barra horizontal 0 → intervalo con el avance de horas acumuladas."""

    def __init__(self, ancho, frac, color, acum, intervalo):
        super().__init__()
        self.ancho, self.frac, self.color, self.acum, self.intervalo = ancho, frac, color, acum, intervalo
        self.height = 30

    def wrap(self, *_):
        return self.ancho, self.height

    def draw(self):
        c = self.canv
        y = 12
        c.setFillColor(colors.HexColor("#E6EBF1"))
        c.roundRect(0, y, self.ancho, 10, 5, stroke=0, fill=1)
        if self.frac > 0:
            c.setFillColor(self.color)
            c.roundRect(0, y, max(10, self.ancho * self.frac), 10, 5, stroke=0, fill=1)
        c.setFillColor(SUAVE)
        c.setFont("Helvetica", 7)
        c.drawString(0, 2, "0 h")
        c.drawRightString(self.ancho, 2, f"{fmt_num(self.intervalo)} h")
        x = min(max(self.ancho * self.frac, 30), self.ancho - 40)
        c.setFillColor(TEXTO)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(x, 24, f"{fmt_num(max(0, self.acum))} h usadas")


def _kpis_horas(filas):
    datos = [(len(filas), "Equipos incluidos", NAVY2),
             (sum(1 for f in filas if f["estado"] == "Vencida"), "PM vencidas", ROJO),
             (sum(1 for f in filas if f["estado"] == "Próxima"), "PM próximas", AMBAR),
             (sum(1 for f in filas if f["estado"] == "En plazo"), "PM en plazo", VERDE)]
    celdas = []
    for v, lbl, col in datos:
        st = ParagraphStyle("kk", parent=EST["kpi"], textColor=col if v else NAVY)
        celdas.append([Paragraph(str(v), st), _p(lbl, "kpil")])
    t = Table([celdas], colWidths=[ANCHO / 4] * 4, rowHeights=[46])
    est = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 12)]
    for i, (_, _, col) in enumerate(datos):
        est += [("BOX", (i, 0), (i, 0), 0.6, BORDE), ("LINEBEFORE", (i, 0), (i, 0), 4, col),
                ("BACKGROUND", (i, 0), (i, 0), colors.white)]
    t.setStyle(TableStyle(est))
    return t


def _bloque(f):
    col = COLOR_ESTADO.get(f["estado"], GRIS)
    tit = f"{f['equipo']}  ·  {f['modelo']}  ·  PM {fmt_tipo(f['pm'])}" if f["hay"] else f"{f['equipo']}  ·  sin historial"
    est_txt = f["estado"] if f["hay"] else "Sin historial"
    cab = Table([[_p(tit, "pmtit"), _chip(est_txt, colors.white)]], colWidths=[ANCHO - 120, 120], rowHeights=[22])
    cab.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), NAVY), ("BACKGROUND", (1, 0), (1, 0), col),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 8)]))
    if not f["hay"]:
        return KeepTogether([cab, _p("El equipo no tiene PM registradas.", "chico"), Spacer(1, 10)])
    faltan = f["faltan"]
    grande = f"{fmt_num(faltan)} h" if faltan > 0 else f"Vencida ({fmt_num(-faltan)} h)"
    st_g = ParagraphStyle("g", parent=EST["kpi"], fontSize=24, leading=27, textColor=col)
    izq = [Paragraph(grande, st_g),
           _p(f"faltan para completar las {fmt_num(f['intervalo'])} h de la PM {fmt_tipo(f['pm'])}" if faltan > 0
              else f"superó las {fmt_num(f['intervalo'])} h de la PM {fmt_tipo(f['pm'])}", "kpil"),
           Spacer(1, 6), BarraAvance(ANCHO * 0.36, f["avance"], col, f["acum"], f["intervalo"])]
    if f["programada"]:
        prog = f"<b>{fmt_fecha(f['fprog'])}</b>"
        ref_lbl = "Horómetro estimado a la fecha programada"
    else:
        prog = "<font color='#D64545'><b>Sin programar</b></font>"
        ref_lbl = f"Horómetro estimado a la fecha sugerida ({fmt_fecha(f['fecha_sug'])})"
    if f["dif_ref"] is None:
        ref = "-"
    elif f["dif_ref"] > 0:
        ref = f"{fmt_num(f['horo_ref'])} h · <font color='#D64545'><b>se pasa {fmt_num(f['dif_ref'])} h</b></font>"
    else:
        ref = f"{fmt_num(f['horo_ref'])} h · <font color='#2E9E5B'><b>llega con {fmt_num(-f['dif_ref'])} h de margen</b></font>"
    lect = (f"{fmt_num(f['horo_hoy'])} h ({fmt_fecha(f['fecha_lect'])})" if f["horo_hoy"] is not None
            else "<font color='#D64545'>sin lectura</font>")
    datos = [
        [_p(f"<b>Fecha programada</b><br/>{prog}"), _p(f"<b>Horómetro de hoy</b><br/>{lect}")],
        [_p(f"<b>Última PM</b><br/>PM {fmt_tipo(f['ult_tipo'])} · {fmt_num(f['ult_horo'])} h · {fmt_fecha(f['ult_fecha'])}"),
         _p(f"<b>Horómetro objetivo</b><br/>{fmt_num(f['objetivo'])} h")],
        [_p(f"<b>Vencimiento proyectado</b><br/>{fmt_fecha(f['fecha_venc']) or '-'} "
            f"({f['dias_rest']} día(s), {fmt_num(f['promedio_proy'], 1)} h/día)"),
         _p(f"<b>{ref_lbl}</b><br/>{ref}")],
    ]
    der = Table(datos, colWidths=[ANCHO * 0.29] * 2)
    der.setStyle(TableStyle([("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    cuerpo = Table([[izq, der]], colWidths=[ANCHO * 0.40, ANCHO * 0.60])
    cuerpo.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("LEFTPADDING", (0, 0), (0, 0), 12),
                                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return KeepTogether([cab, cuerpo, Spacer(1, 12)])


def exportar_horas_pdf(m: Motor, equipos: list[str], ruta: str, usuario: str) -> list[dict]:
    filas = m.horas_pm(equipos)
    from .tema import dibujar
    logo = ImageReader(dibujar("logo").resize((128, 128)))
    emitido = dt.datetime.now()
    hoy = fmt_fecha(m.hoy)
    pagina = marco_pagina("HORAS PARA LA PM PROGRAMADA", f"{' · '.join(equipos)}  ·  AL {hoy}",
                          f"Planificación PM · Horas para la PM · {hoy}", usuario, emitido, logo)
    doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=95,
                            bottomMargin=45, title="Horas para la PM programada", author=usuario,
                            subject="Horas restantes para la PM de cada equipo")
    h = _seccion("Resumen")
    h.append(_kpis_horas([f for f in filas if f["hay"]]))
    h.append(Spacer(1, 8))
    tab, extra = [], []
    for i, f in enumerate(filas, start=1):
        col = COLOR_ESTADO.get(f["estado"], GRIS)
        tab.append([_p(f"<b>{f['equipo']}</b>"), f"PM {fmt_tipo(f['pm'])}" if f["hay"] else "-",
                    fmt_fecha(f["fprog"]) or "Sin programar",
                    fmt_num(f["horo_hoy"]) + " h" if f["horo_hoy"] is not None else "-",
                    fmt_num(f["objetivo"]) + " h" if f["hay"] else "-",
                    _p(f"<b>{fmt_num(f['faltan'])} h</b>") if f["hay"] else "-",
                    _chip(f["estado"] if f["hay"] else "Sin historial", col)])
        extra.append(("BACKGROUND", (6, i), (6, i), CLARO.get(col, colors.white)))
    h.append(_tabla(["Equipo", "PM", "Fecha programada", "Horómetro hoy", "Objetivo", "Horas que faltan", "Estado"],
                    tab, [ANCHO * x for x in (0.11, 0.11, 0.17, 0.16, 0.15, 0.15, 0.15)], extra))
    h.append(Spacer(1, 4))
    h.append(_p(f"Horas que faltan = horómetro objetivo (última PM + {fmt_num(filas[0]['intervalo'] if filas else 250)} h) "
                "− horómetro de hoy. Estimaciones con el avance proyectado (promedio real de las últimas PM + avance "
                "extra de Configuración).", "chico"))
    h += _seccion("Detalle por equipo")
    for f in filas:
        h.append(_bloque(f))
    doc.build(h, onFirstPage=pagina, onLaterPages=pagina)
    return filas


__all__ = ["exportar_horas_pdf"]
