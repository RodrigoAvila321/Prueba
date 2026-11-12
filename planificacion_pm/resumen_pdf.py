"""Resumen de PM ejecutadas en PDF, con diseño de mantenimiento (portada, puntos clave, cumplimiento
de horas y fechas, aceites cambiados y su estado, firmas)."""
from __future__ import annotations

import datetime as dt
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from .motor import Motor
from .util import ORIGEN_FUERA, ORIGEN_IND, ORIGEN_NO, ORIGEN_PM, es_num, fmt_fecha, fmt_num, fmt_tipo, mismo_texto

NAVY = colors.HexColor("#15233A")
NAVY2 = colors.HexColor("#22354F")
ACENTO = colors.HexColor("#F28C28")
AMARILLO = colors.HexColor("#F6C343")
VERDE = colors.HexColor("#2E9E5B")
ROJO = colors.HexColor("#D64545")
AZUL = colors.HexColor("#1F6FB2")
GRIS = colors.HexColor("#8A96A3")
SUAVE = colors.HexColor("#6B7785")
TEXTO = colors.HexColor("#1F2A37")
BORDE = colors.HexColor("#D8E0E9")
FONDO = colors.HexColor("#F4F7FA")
CLARO = {VERDE: colors.HexColor("#DFF3E6"), ROJO: colors.HexColor("#FADBD8"), AZUL: colors.HexColor("#DCEAF7"),
         ACENTO: colors.HexColor("#FDEBD8"), GRIS: colors.HexColor("#ECEFF3")}


# =============================================================== datos
def _sig(x: float) -> str:
    return f"+{fmt_num(x)}" if x > 0 else (f"-{fmt_num(-x)}" if x < 0 else "0")


def datos_resumen(m: Motor, d1: dt.date, d2: dt.date) -> dict:
    tol = float(m.p.get("tol_pm", 10) or 0)
    intervalo = float(m.p["intervalo"])
    pms = []
    for eq, lista in m.hist_eq.items():
        modelo = m.modelo_de(eq) or (lista[0]["modelo"] if lista else "")
        for i, f in enumerate(lista):
            if not (f["fecha"] and d1 <= f["fecha"] <= d2):
                continue
            prev = lista[i - 1] if i > 0 else None
            horo = float(f["horo"] or 0)
            objetivo = float(prev["horo"]) + intervalo if prev and es_num(prev["horo"]) else None
            dif = horo - objetivo if objetivo is not None else None
            if dif is None:
                est_h, col_h = "Sin PM anterior", GRIS
            elif abs(dif) <= tol:
                est_h, col_h = "A tiempo", VERDE
            elif dif < 0:
                est_h, col_h = f"Adelantada {fmt_num(-dif)} h", AZUL
            else:
                est_h, col_h = f"Atrasada {fmt_num(dif)} h", ROJO
            if not f["fprog"]:
                est_f, col_f, dias = "Sin programación", GRIS, None
            else:
                dias = (f["fecha"] - f["fprog"]).days
                if dias == 0:
                    est_f, col_f = "En fecha", VERDE
                elif dias < 0:
                    est_f, col_f = f"Adelantada {-dias} día(s)", AZUL
                else:
                    est_f, col_f = f"Postergada {dias} día(s)", ROJO
            aceites = []
            for a in m.ac:
                if a["id_pm"] != f["id"] or a["equipo"].strip() != eq:
                    continue
                freq = next((float(c["frecuencia"] or 0) for c in m.aceites_cfg
                             if c["modelo"] == modelo and mismo_texto(c["componente"], a["comp"])), None)
                h = a["horas_ac"]
                if a["origen"] == ORIGEN_NO:
                    est, col = "Pendiente (no cambiado)", ROJO
                elif es_num(h) and freq:
                    d = float(h) - freq
                    if abs(d) <= tol:
                        est, col = "A tiempo", VERDE
                    elif d > 0:
                        est, col = f"Atrasado {fmt_num(d)} h", ROJO
                    else:
                        est, col = f"Adelantado {fmt_num(-d)} h", AZUL
                else:
                    est, col = "Primer registro", GRIS
                aceites.append(dict(comp=a["comp"], freq=freq, horas=h, horo=a["horo"], origen=a["origen"],
                                    estado=est, color=col))
            pms.append(dict(equipo=eq, modelo=modelo, tipo=f["tipo"], fecha=f["fecha"], horo=horo, objetivo=objetivo,
                            dif=dif, est_h=est_h, col_h=col_h, fprog=f["fprog"], dias=dias, est_f=est_f, col_f=col_f,
                            horas=f["horas"], obs=f["obs"] or "", por=f["reg_por"] or "", aceites=aceites))
    pms.sort(key=lambda x: (x["fecha"], x["equipo"]))
    individuales = [a for a in m.ac if a["origen"] == ORIGEN_IND and a["reg_el"] and d1 <= a["reg_el"].date() <= d2]
    por_equipo = []
    for eq in m.lista_equipos():
        e = m.estado(eq)
        de_eq = [p for p in pms if p["equipo"] == eq]
        difs = [p["dif"] for p in de_eq if p["dif"] is not None]
        por_equipo.append(dict(equipo=eq, modelo=e["modelo"], n=len(de_eq),
                               dif=(sum(difs) / len(difs)) if difs else None,
                               pm_actual=e["sugerido"] if e["n"] else None, objetivo=e["proyectado"] if e["n"] else None,
                               venc=e["fecha_proy"] if e["n"] and e["con_lectura"] else None,
                               fprog=e["fprog"], estado=e["estado"], rest=e["rest"]))
    todos_ac = [a for p in pms for a in p["aceites"]]
    cambiados = [a for a in todos_ac if a["origen"] in (ORIGEN_PM, ORIGEN_FUERA)]
    difs = [p["dif"] for p in pms if p["dif"] is not None]
    k = dict(
        n_pm=len(pms), equipos=sorted({p["equipo"] for p in pms}),
        a_tiempo=sum(1 for p in pms if p["col_h"] is VERDE), adelantadas=sum(1 for p in pms if p["col_h"] is AZUL),
        atrasadas=sum(1 for p in pms if p["col_h"] is ROJO), aceites=len(cambiados),
        ac_atraso=sum(1 for a in cambiados if a["color"] is ROJO),
        ac_pend=sum(1 for a in todos_ac if a["origen"] == ORIGEN_NO),
        dif_prom=(sum(difs) / len(difs)) if difs else None, individuales=len(individuales))
    return dict(d1=d1, d2=d2, tol=tol, intervalo=intervalo, pms=pms, individuales=individuales,
                por_equipo=por_equipo, kpi=k)


def puntos_clave(r: dict) -> list[str]:
    k, pms = r["kpi"], r["pms"]
    out = []
    if not pms:
        return ["No se registraron PM ejecutadas en el período."]
    out.append(f"Se ejecutaron <b>{k['n_pm']} PM</b> en <b>{len(k['equipos'])} equipo(s)</b>: {', '.join(k['equipos'])}.")
    out.append(f"Cumplimiento en horas (tolerancia ±{fmt_num(r['tol'])} h): <b>{k['a_tiempo']}</b> a tiempo, "
               f"<b>{k['adelantadas']}</b> adelantadas y <b>{k['atrasadas']}</b> atrasadas.")
    con_dif = [p for p in pms if p["dif"] is not None]
    if con_dif:
        a = min(con_dif, key=lambda p: p["dif"])
        b = max(con_dif, key=lambda p: p["dif"])
        if a["dif"] < -r["tol"]:
            out.append(f"Mayor adelanto: <b>{a['equipo']} PM {fmt_tipo(a['tipo'])}</b> del {fmt_fecha(a['fecha'])}, "
                       f"{fmt_num(-a['dif'])} h antes del objetivo.")
        if b["dif"] > r["tol"]:
            out.append(f"Mayor atraso: <b>{b['equipo']} PM {fmt_tipo(b['tipo'])}</b> del {fmt_fecha(b['fecha'])}, "
                       f"{fmt_num(b['dif'])} h después del objetivo.")
    out.append(f"Se cambiaron <b>{k['aceites']}</b> aceites en las PM; <b>{k['ac_atraso']}</b> con atraso respecto de su "
               f"frecuencia.")
    pend = [(p["equipo"], a["comp"]) for p in pms for a in p["aceites"] if a["origen"] == ORIGEN_NO]
    if pend:
        out.append(f"<font color='#D64545'><b>Aceites pendientes ({len(pend)}):</b></font> "
                   + "; ".join(f"{e} {escape(c)}" for e, c in pend) + ".")
    if k["individuales"]:
        out.append(f"Además se registraron <b>{k['individuales']}</b> cambios de aceite individuales (fuera de PM).")
    prox = [x for x in r["por_equipo"] if x["pm_actual"] and x["venc"]]
    prox.sort(key=lambda x: x["venc"])
    if prox:
        out.append("Próximas PM: " + "; ".join(f"<b>{x['equipo']}</b> PM {fmt_tipo(x['pm_actual'])} "
                                              f"({fmt_fecha(x['venc'])})" for x in prox[:5]) + ".")
    return out


# =============================================================== PDF
EST = {
    "normal": ParagraphStyle("n", fontName="Helvetica", fontSize=9, leading=12, textColor=TEXTO),
    "chico": ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10, textColor=SUAVE),
    "celda": ParagraphStyle("ce", fontName="Helvetica", fontSize=8, leading=10, textColor=TEXTO),
    "celdab": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=TEXTO),
    "sec": ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=NAVY),
    "kpi": ParagraphStyle("k", fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=NAVY),
    "kpil": ParagraphStyle("kl", fontName="Helvetica", fontSize=8, leading=10, textColor=SUAVE),
    "bullet": ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13, textColor=TEXTO, leftIndent=12,
                             bulletIndent=2),
    "pmtit": ParagraphStyle("p", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.white),
    "chip": ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=TA_CENTER),
}
ANCHO = letter[0] - 2 * 15 * mm


def _p(txt, est="celda"):
    return Paragraph(txt, EST[est])


def _seccion(titulo):
    t = Table([["", _p(titulo, "sec")]], colWidths=[4, ANCHO - 4], rowHeights=[20])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ACENTO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (1, 0), (1, 0), 8)]))
    return [Spacer(1, 10), t, Spacer(1, 6)]


def _chip(txt, col):
    st = ParagraphStyle("x", parent=EST["chip"], textColor=col)
    return Paragraph(escape(txt), st)


def _kpis(k):
    datos = [(k["n_pm"], "PM ejecutadas", NAVY2), (len(k["equipos"]), "Equipos intervenidos", NAVY2),
             (k["a_tiempo"], "PM a tiempo", VERDE), (k["adelantadas"], "PM adelantadas", AZUL),
             (k["atrasadas"], "PM atrasadas", ROJO), (k["aceites"], "Aceites cambiados", ACENTO),
             (k["ac_atraso"], "Aceites con atraso", ROJO), (k["ac_pend"], "Aceites pendientes", ROJO)]
    celdas = []
    for v, lbl, col in datos:
        st = ParagraphStyle("kk", parent=EST["kpi"], textColor=col if v else NAVY)
        celdas.append([Paragraph(str(v), st), _p(lbl, "kpil")])
    w = ANCHO / 4
    filas = [celdas[:4], celdas[4:]]
    t = Table(filas, colWidths=[w] * 4, rowHeights=[46, 46])
    est = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 12)]
    for i, (_, _, col) in enumerate(datos):
        c, r = i % 4, i // 4
        est += [("BOX", (c, r), (c, r), 0.6, BORDE), ("LINEBEFORE", (c, r), (c, r), 4, col),
                ("BACKGROUND", (c, r), (c, r), colors.white)]
    t.setStyle(TableStyle(est))
    return t


def _tabla(encabezado, filas, anchos, extra=()):
    t = Table([encabezado] + filas, colWidths=anchos, repeatRows=1)
    est = [("BACKGROUND", (0, 0), (-1, 0), NAVY2), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
           ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for i in range(1, len(filas) + 1):
        if i % 2 == 0:
            est.append(("BACKGROUND", (0, i), (-1, i), FONDO))
    t.setStyle(TableStyle(est + list(extra)))
    return t


def _bloque_pm(p, intervalo):
    tit = (f"{p['equipo']}  ·  PM {fmt_tipo(p['tipo'])}  ·  {p['modelo']}  ·  {fmt_fecha(p['fecha'])}  ·  "
           f"horómetro {fmt_num(p['horo'])} h")
    cab = Table([[_p(escape(tit), "pmtit"), _chip(p["est_h"], colors.white)]],
                colWidths=[ANCHO - 120, 120], rowHeights=[22])
    cab.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), NAVY), ("BACKGROUND", (1, 0), (1, 0), p["col_h"]),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 8)]))
    obj = f"{fmt_num(p['objetivo'])} h" if p["objetivo"] is not None else "-"
    dif = f"{_sig(p['dif'])} h" if p["dif"] is not None else "-"
    info = [[_p("<b>Horómetro objetivo</b><br/>" + obj), _p("<b>Desviación vs objetivo</b><br/>" + dif),
             _p("<b>Horas desde PM anterior</b><br/>" + (fmt_num(p["horas"]) + " h" if es_num(p["horas"]) else "-")),
             _p("<b>Fecha programada</b><br/>" + (fmt_fecha(p["fprog"]) or "No programada")),
             [_p("<b>Cumplimiento fecha</b>"), _chip(p["est_f"], p["col_f"])]]]
    ti = Table(info, colWidths=[ANCHO / 5] * 5)
    ti.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), colors.white)]))
    partes = [cab, ti]
    if p["aceites"]:
        filas, extra = [], []
        for i, a in enumerate(p["aceites"], start=1):
            filas.append([_p(escape(a["comp"])), fmt_num(a["freq"]) + " h" if a["freq"] else "-",
                          fmt_num(a["horo"]) + " h" if es_num(a["horo"]) else "-",
                          fmt_num(a["horas"]) + " h" if es_num(a["horas"]) else (a["horas"] or "-"),
                          a["origen"], _chip(a["estado"], a["color"])])
            extra.append(("BACKGROUND", (5, i), (5, i), CLARO.get(a["color"], colors.white)))
        partes.append(_tabla(["Aceite / componente", "Frecuencia", "Horómetro cambio", "Horas al cambio", "Origen",
                              "Estado"], filas, [ANCHO * x for x in (0.27, 0.10, 0.155, 0.135, 0.12, 0.22)], extra))
    else:
        partes.append(_p("Sin registros de aceite asociados a esta PM.", "chico"))
    if p["obs"]:
        partes.append(_p(f"<b>Observación:</b> {escape(p['obs'])}", "chico"))
    partes.append(_p(f"Registrada por {escape(p['por'])}" if p["por"] else "", "chico"))
    return KeepTogether(partes + [Spacer(1, 10)])


def exportar_resumen_pdf(m: Motor, d1: dt.date, d2: dt.date, turno: str, ruta: str, usuario: str) -> dict:
    r = datos_resumen(m, d1, d2)
    from .tema import dibujar  # import diferido: usa Pillow
    logo = ImageReader(dibujar("logo").resize((128, 128)))
    emitido = dt.datetime.now()

    def pagina(c, doc):
        w, h = letter
        c.saveState()
        c.setFillColor(NAVY)
        c.rect(0, h - 70, w, 70, stroke=0, fill=1)
        c.drawImage(logo, 15 * mm, h - 58, 44, 44, mask="auto")
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(15 * mm + 54, h - 33, "RESUMEN DE MANTENCIONES PREVENTIVAS")
        c.setFillColor(ACENTO)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm + 54, h - 50, f"{turno.upper()}  ·  {fmt_fecha(d1)} al {fmt_fecha(d2)}")
        c.setFillColor(colors.HexColor("#C5D0DE"))
        c.setFont("Helvetica", 8)
        c.drawRightString(w - 15 * mm, h - 30, f"Emitido el {emitido:%d-%m-%Y %H:%M}")
        c.drawRightString(w - 15 * mm, h - 42, f"por {usuario}")
        c.drawRightString(w - 15 * mm, h - 54, "Equipos de perforación")
        # franja de seguridad
        c.setFillColor(AMARILLO)
        c.rect(0, h - 77, w, 7, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#222831"))
        x = -7
        while x < w:
            p = c.beginPath()
            p.moveTo(x, h - 77)
            p.lineTo(x + 7, h - 70)
            p.lineTo(x + 14, h - 70)
            p.lineTo(x + 7, h - 77)
            p.close()
            c.drawPath(p, stroke=0, fill=1)
            x += 18
        # pie
        c.setStrokeColor(BORDE)
        c.line(15 * mm, 30, w - 15 * mm, 30)
        c.setFillColor(SUAVE)
        c.setFont("Helvetica", 7.5)
        c.drawString(15 * mm, 18, f"Planificación PM · Resumen {turno} · {fmt_fecha(d1)} al {fmt_fecha(d2)}")
        c.drawRightString(w - 15 * mm, 18, f"Página {doc.page}")
        c.restoreState()

    doc = SimpleDocTemplate(ruta, pagesize=letter, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=95,
                            bottomMargin=45, title=f"Resumen de PM {turno}", author=usuario,
                            subject="Mantenciones preventivas ejecutadas")
    h = []
    h += _seccion("Puntos clave")
    h.append(_kpis(r["kpi"]))
    h.append(Spacer(1, 8))
    for t in puntos_clave(r):
        h.append(Paragraph(t, EST["bullet"], bulletText="•"))
    if r["kpi"]["dif_prom"] is not None:
        h.append(Paragraph(f"Desviación promedio respecto del objetivo de {fmt_num(r['intervalo'])} h: "
                           f"<b>{_sig(r['kpi']['dif_prom'])} h</b> (negativo = adelantada).", EST["bullet"],
                           bulletText="•"))

    h += _seccion("Resumen por equipo")
    filas, extra = [], []
    col_est = {"Vencida": ROJO, "Próxima": ACENTO, "En plazo": VERDE}
    for i, x in enumerate(r["por_equipo"], start=1):
        col = col_est.get(x["estado"], GRIS)
        filas.append([_p(f"<b>{x['equipo']}</b>"), x["modelo"], str(x["n"]),
                      f"{_sig(x['dif'])} h" if x["dif"] is not None else "-",
                      f"PM {fmt_tipo(x['pm_actual'])}" if x["pm_actual"] else "-",
                      fmt_num(x["objetivo"]) + " h" if x["objetivo"] else "-",
                      fmt_fecha(x["venc"]) or "-", fmt_fecha(x["fprog"]) or "No programada",
                      _chip(x["estado"], col)])
        extra.append(("BACKGROUND", (8, i), (8, i), CLARO.get(col, colors.white)))
    h.append(_tabla(["Equipo", "Modelo", "PM período", "Desv. prom.", "PM actual", "Objetivo", "Vencimiento",
                     "Programada", "Estado"], filas,
                    [ANCHO * x for x in (0.08, 0.09, 0.09, 0.10, 0.10, 0.11, 0.12, 0.13, 0.18)], extra))

    h += _seccion("Detalle de las PM ejecutadas")
    h.append(_p(f"Desviación = horómetro real - (horómetro de la PM anterior + {fmt_num(r['intervalo'])} h). "
                f"«A tiempo» = dentro de ±{fmt_num(r['tol'])} h. Aceites: horas acumuladas al cambio comparadas con "
                "su frecuencia.", "chico"))
    h.append(Spacer(1, 6))
    if r["pms"]:
        for p in r["pms"]:
            h.append(_bloque_pm(p, r["intervalo"]))
    else:
        h.append(_p("No se registraron PM ejecutadas en el período.", "normal"))

    if r["individuales"]:
        h += _seccion("Cambios de aceite individuales (fuera de PM)")
        filas = [[a["equipo"], _p(escape(a["comp"])), fmt_num(a["horo"]) + " h" if es_num(a["horo"]) else "-",
                  fmt_num(a["horas_ac"]) + " h" if es_num(a["horas_ac"]) else (a["horas_ac"] or "-"),
                  a["reg_el"].strftime("%d-%m-%Y")] for a in r["individuales"]]
        h.append(_tabla(["Equipo", "Componente", "Horómetro", "Horas al cambio", "Fecha"], filas,
                        [ANCHO * x for x in (0.12, 0.40, 0.16, 0.16, 0.16)]))

    h.append(Spacer(1, 40))
    firmas = Table([["", "", ""], [_p(f"<b>Responsable {escape(turno)}</b>"), "", _p("<b>Supervisor</b>")],
                    [_p("Nombre y firma", "chico"), "", _p("Nombre y firma", "chico")]],
                   colWidths=[ANCHO * 0.4, ANCHO * 0.2, ANCHO * 0.4], rowHeights=[30, 14, 12])
    firmas.setStyle(TableStyle([("LINEBELOW", (0, 0), (0, 0), 0.8, TEXTO), ("LINEBELOW", (2, 0), (2, 0), 0.8, TEXTO),
                                ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    h.append(KeepTogether([firmas]))
    doc.build(h, onFirstPage=pagina, onLaterPages=pagina)
    return r
