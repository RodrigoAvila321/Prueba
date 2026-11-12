"""Importa los datos y la configuración desde el libro Excel original (.xlsm / .xlsx)."""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl

from .db import PARAMS_DEF, Repositorio
from .util import a_fecha, a_fechahora, es_num

_PARAM_NOMBRES = {
    "intervalo": "prmIntervalo", "horas_dia": "prmHorasDia", "pm_prom": "prmPMProm",
    "alerta_pm": "prmAlertaPM", "alerta_aceite": "prmAlertaAceite", "muestra": "prmMuestra",
    "tarro": "prmTarro", "margen": "prmMargen", "margen_prog": "prmMargenProg",
    "avance_extra": "prmAvanceExtra",
}


class LibroOrigen:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self.wb = openpyxl.load_workbook(self.ruta, data_only=True)

    def rango(self, nombre: str):
        dn = self.wb.defined_names.get(nombre)
        if dn is None:
            raise KeyError(f"No existe el nombre «{nombre}» en el libro.")
        hoja, ref = next(iter(dn.destinations))
        ws = self.wb[hoja]
        celdas = ws[ref.replace("$", "")]
        if not isinstance(celdas, tuple):
            return [[celdas.value]]
        if celdas and not isinstance(celdas[0], tuple):
            celdas = (celdas,)
        return [[c.value for c in fila] for fila in celdas]

    def valor(self, nombre: str):
        return self.rango(nombre)[0][0]

    def tiene(self, nombre: str) -> bool:
        return self.wb.defined_names.get(nombre) is not None


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def _num(v):
    return float(v) if es_num(v) else None


def importar_libro(ruta: str | Path, repo: Repositorio, incluir_datos: bool = True) -> dict:
    """Carga configuración y (opcionalmente) Historial, Aceites, Lecturas y Programación.
    Devuelve un resumen con la cantidad de registros importados."""
    lib = LibroOrigen(ruta)
    res = {}
    with repo.transaccion():
        if incluir_datos:
            repo.vaciar_todo()
        # ---------------- parámetros
        params = {}
        for clave, _, defecto in PARAMS_DEF:
            n = _PARAM_NOMBRES[clave]
            v = lib.valor(n) if lib.tiene(n) else None
            params[clave] = float(v) if es_num(v) else defecto
        params["usuario"] = ""
        repo.set_config("params", params, commit=False)

        # ---------------- equipos
        equipos = [{"equipo": _txt(r[0]), "modelo": _txt(r[1]), "faena": _txt(r[2])}
                   for r in lib.rango("tblEquipos") if _txt(r[0])]
        repo.set_config("equipos", equipos, commit=False)

        # ---------------- ciclo
        ciclos = []
        mods = lib.rango("cfgCicloModelo")
        seqs = lib.rango("cfgCicloSeq")
        largos = lib.rango("cfgCicloLargo")
        cierres = lib.rango("cfgCicloCierre")
        for i, m in enumerate(mods):
            if not _txt(m[0]):
                continue
            fila = {"modelo": _txt(m[0])}
            for j, v in enumerate(seqs[i]):
                fila[f"pos{j + 1}"] = _num(v)
            fila["largo"] = int(largos[i][0]) if es_num(largos[i][0]) else 3
            fila["cierres"] = _txt(cierres[i][0])
            ciclos.append(fila)
        repo.set_config("ciclos", ciclos, commit=False)

        # ---------------- tipos válidos por modelo
        hdr = lib.rango("cfgTiposHdr")[0]
        cuerpo = lib.rango("cfgTipos")
        tipos = []
        for j, m in enumerate(hdr):
            if _txt(m):
                lst = [int(f[j]) for f in cuerpo if es_num(f[j])]
                tipos.append({"modelo": _txt(m), "tipos": ",".join(str(t) for t in lst)})
        repo.set_config("tipos", tipos, commit=False)

        # ---------------- aceites por modelo
        ac = []
        for m, c, f, t in zip(lib.rango("cfgAcModelo"), lib.rango("cfgAcComp"),
                              lib.rango("cfgAcFreq"), lib.rango("cfgAcTexto")):
            if _txt(m[0]) and _txt(c[0]):
                ac.append({"modelo": _txt(m[0]), "componente": _txt(c[0]), "frecuencia": _num(f[0]),
                           "texto": _txt(t[0])})
        repo.set_config("aceites_cfg", ac, commit=False)

        # ---------------- consumo por PM
        tipos_hdr = [int(v) for v in lib.rango("cfgConsTiposHdr")[0] if es_num(v)]
        repo.set_config("consumo_tipos", tipos_hdr, commit=False)
        ws = lib.wb["Configuración"]
        cons = []
        mod_r = lib.rango("cfgConsMod")
        flags = lib.rango("cfgConsFlags")
        dn = lib.wb.defined_names["cfgConsMod"]
        _, ref = next(iter(dn.destinations))
        fila0 = openpyxl.utils.cell.range_boundaries(ref.replace("$", ""))[1]
        for i, m in enumerate(mod_r):
            if not _txt(m[0]):
                continue
            r = fila0 + i
            fila = {"modelo": _txt(m[0]), "sistema": _txt(ws.cell(r, 3).value),
                    "lubricante": _txt(ws.cell(r, 4).value), "parte": _txt(ws.cell(r, 5).value),
                    "litros": _num(ws.cell(r, 6).value) or 0.0}
            for j, t in enumerate(tipos_hdr):
                fila[str(t)] = _num(flags[i][j]) or 0.0
            cons.append(fila)
        repo.set_config("consumo", cons, commit=False)

        # ---------------- consumo diario
        diario = []
        _, ref = next(iter(lib.wb.defined_names["dEquipo"].destinations))
        fila_d = openpyxl.utils.cell.range_boundaries(ref.replace("$", ""))[1]
        for i, e in enumerate(lib.rango("dEquipo")):
            if _txt(e[0]):
                diario.append({"equipo": _txt(e[0]), "parte": _txt(lib.rango("dParte")[i][0]),
                               "lubricante": _txt(ws.cell(fila_d + i, 4).value),
                               "litros_dia": _num(lib.rango("dLitrosDia")[i][0]) or 0.0})
        repo.set_config("diario", diario, commit=False)

        # ---------------- kits PM
        kits = []
        if "Kits PM" in lib.wb.sheetnames:
            wk = lib.wb["Kits PM"]
            r = 5
            while _txt(wk.cell(r, 3).value):
                v = [wk.cell(r, c).value for c in range(3, 15)]
                kits.append({"modelo": _txt(v[0]), "tipo": _num(v[1]), "cuadro": int(v[2] or 1),
                             "kit": _txt(v[3]), "ubic_kit": _txt(v[4]), "equipos": _txt(v[5]),
                             "linea": int(v[6] or 0), "tipo_linea": _txt(v[7]).upper(),
                             "np": _txt(v[8]), "cant": _num(v[9]), "ubic": _txt(v[10]), "com": _txt(v[11])})
                r += 1
        repo.set_config("kits", kits, commit=False)

        # ---------------- descripciones de repuestos
        desc = []
        if "Descripciones repuestos" in lib.wb.sheetnames:
            wd = lib.wb["Descripciones repuestos"]
            r = 5
            while _txt(wd.cell(r, 2).value):
                desc.append({"np": _txt(wd.cell(r, 2).value), "descripcion": _txt(wd.cell(r, 3).value)})
                r += 1
        repo.set_config("descripciones", desc, commit=False)

        # ---------------- períodos guardados
        per = {}
        for n, k in (("inDesde", "desde"), ("inHasta", "hasta"), ("inSemIni", "sem_ini"), ("inSemN", "sem_n")):
            if lib.tiene(n):
                v = lib.valor(n)
                per[k] = int(v) if k == "sem_n" and es_num(v) else (a_fecha(v).isoformat() if a_fecha(v) else None)
        repo.set_config("periodos", per, commit=False)
        if lib.tiene("selEquipo"):
            repo.set_config("equipo_sel", _txt(lib.valor("selEquipo")), commit=False)

        # ---------------- plantillas de solicitud de análisis
        modelos = {e["modelo"] for e in equipos}
        n_pl = 0
        for m in sorted(modelos):
            hoja = f"Formato {m}"
            if hoja in lib.wb.sheetnames:
                repo.set_plantilla(m, extraer_hoja(lib.ruta, hoja))
                n_pl += 1
        res["plantillas"] = n_pl

        if not incluir_datos:
            return res

        # ---------------- historial
        wh = lib.wb["Historial"]
        tabla = wh.tables["tblHistorial"]
        r1 = openpyxl.utils.cell.range_boundaries(tabla.ref)[1] + 1
        n = 0
        for r in range(r1, wh.max_row + 1):
            v = [wh.cell(r, c).value for c in range(1, 16)]
            if not _txt(v[1]):
                continue
            repo.agregar_historial({
                "id": int(v[0]) if es_num(v[0]) else 0, "equipo": _txt(v[1]), "modelo": _txt(v[2]),
                "faena": _txt(v[3]), "tipo": _num(v[4]), "fecha": a_fecha(v[5]), "horo": _num(v[6]),
                "horas": _num(v[7]), "fprog": a_fecha(v[8]), "obs": _txt(v[9]),
                "reg_el": a_fechahora(v[10]), "reg_por": _txt(v[11]),
                "pos": int(v[14]) if es_num(v[14]) else None})
            n += 1
        res["historial"] = n

        # ---------------- aceites
        wa = lib.wb["Aceites"]
        tabla = wa.tables["tblCambiosAceite"]
        r1 = openpyxl.utils.cell.range_boundaries(tabla.ref)[1] + 1
        n = 0
        for r in range(r1, wa.max_row + 1):
            v = [wa.cell(r, c).value for c in range(1, 8)]
            if not _txt(v[1]):
                continue
            h = v[6]
            repo.agregar_aceite({"id_pm": int(v[0]) if es_num(v[0]) else 0, "equipo": _txt(v[1]),
                                 "comp": _txt(v[2]), "horo": _num(v[3]), "origen": _txt(v[4]),
                                 "reg_el": a_fechahora(v[5]),
                                 "horas_ac": float(h) if es_num(h) else (_txt(h) or None)})
            n += 1
        res["aceites"] = n

        # ---------------- lecturas y programación
        for e, h, f, p in zip(lib.rango("lEquipo"), lib.rango("lHoro"), lib.rango("lFecha"), lib.rango("lPor")):
            if _txt(e[0]):
                repo.set_lectura(_txt(e[0]), _num(h[0]), a_fecha(f[0]), _txt(p[0]))
        for e, t, h, f, a in zip(lib.rango("pEquipo"), lib.rango("pTipo"), lib.rango("pHoroObj"),
                                 lib.rango("pFecha"), lib.rango("pActualizado")):
            if _txt(e[0]):
                repo.set_programacion(_txt(e[0]), _num(t[0]), _num(h[0]), a_fecha(f[0]), a_fechahora(a[0]))
    return res


def extraer_hoja(ruta: Path, hoja: str) -> bytes:
    """Copia una hoja (con su formato) a un libro .xlsx independiente, en memoria."""
    wb = openpyxl.load_workbook(ruta)
    for ws in list(wb.worksheets):
        if ws.title != hoja:
            wb.remove(ws)
    ws = wb[hoja]
    ws.sheet_state = "visible"
    wb.active = 0
    for n in list(wb.defined_names):
        del wb.defined_names[n]
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
