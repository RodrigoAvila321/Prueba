"""Motor de cálculo. Reproduce las fórmulas de las hojas Calc, CalcFlota, Panel, Proyección,
Proyección aceites, Aceites por semanas y Kits a solicitar del libro original."""
from __future__ import annotations

import datetime as dt
from collections import OrderedDict, defaultdict

from .db import Repositorio
from .util import (ORIGEN_NO, es_num, fmt_tipo, mismo_texto, primer_dia_mes, redondear,
                   redondear_arriba, semana_iso)

N_PROY_EQUIPO = 120     # PM proyectadas por equipo (CalcFlota)
N_PROY_PANEL = 30       # PM de la hoja Proyección
SEM_MAX = 52
MESES_MAX = 60
DIA = dt.timedelta(days=1)


def _d(n) -> dt.timedelta:
    return dt.timedelta(days=int(n))


def etiqueta_corta(d: dt.date) -> str:
    return f"{d.day:02d}-{d.month:02d}-{str(d.year)[-2:]}"


def categoria_suelto(com: str) -> str:
    com = (com or "").lower()
    if "adicional" in com:
        return "adicional"
    if "separado" in com:
        return "por separado"
    if "bodega" in com:
        return "bodega"
    return "suelto" if com == "" else com


class Motor:
    def __init__(self, repo: Repositorio, hoy: dt.date | None = None):
        self.repo = repo
        self._hoy = hoy
        self.recargar()

    # ------------------------------------------------------------------ datos
    @property
    def hoy(self) -> dt.date:
        return self._hoy or dt.date.today()

    def recargar(self):
        r = self.repo
        self.p = r.params()
        self.equipos = r.get_config("equipos", [])
        self.ciclos = {c["modelo"]: c for c in r.get_config("ciclos", [])}
        self.tipos_cfg = {t["modelo"]: [int(x) for x in str(t["tipos"]).replace(" ", "").split(",") if x]
                          for t in r.get_config("tipos", [])}
        self.aceites_cfg = r.get_config("aceites_cfg", [])
        self.consumo = r.get_config("consumo", [])
        self.consumo_tipos = [int(t) for t in r.get_config("consumo_tipos", [])]
        self.diario = r.get_config("diario", [])
        self.kits = r.get_config("kits", [])
        self.descripciones = {d["np"]: d["descripcion"] for d in r.get_config("descripciones", [])}
        self.hist = r.historial()
        self.ac = r.aceites()
        self.lecturas = r.lecturas()
        self.prog = r.programacion()
        self.hist_eq = defaultdict(list)
        for f in self.hist:
            self.hist_eq[f["equipo"].strip()].append(f)
        self._proy_cache = {}
        self._estado_cache = {}

    # ------------------------------------------------------------- consultas
    def lista_equipos(self) -> list[str]:
        return [e["equipo"] for e in self.equipos]

    def equipo_info(self, eq: str) -> dict | None:
        for e in self.equipos:
            if e["equipo"] == eq:
                return e
        return None

    def modelo_de(self, eq: str) -> str:
        e = self.equipo_info(eq)
        return e["modelo"] if e else ""

    def faena_de(self, eq: str) -> str:
        e = self.equipo_info(eq)
        return e["faena"] if e else ""

    def tipos_validos(self, modelo: str) -> list[int]:
        return self.tipos_cfg.get(modelo, [])

    def ciclo_de(self, modelo: str) -> tuple[int, str, dict | None]:
        c = self.ciclos.get(modelo)
        if not c:
            return 3, "1500,3000,5000", None
        return int(c.get("largo") or 3), str(c.get("cierres") or "").replace(" ", ""), c

    def valor_ciclo(self, modelo: str, pos: int) -> float:
        _, _, c = self.ciclo_de(modelo)
        if c is None:
            return 500.0
        v = c.get(f"pos{pos}")
        return float(v) if es_num(v) else 0.0

    def tipo_cierre(self, modelo: str) -> int:
        t = self.tipos_validos(modelo)
        return int(t[-1]) if t else 1500

    def partes_pm(self) -> list[str]:
        return sorted({c["parte"] for c in self.consumo if c.get("parte")})

    def partes_diario(self) -> list[str]:
        return sorted({d["parte"] for d in self.diario if d.get("parte")})

    def partes(self) -> list[str]:
        return sorted(set(self.partes_pm()) | set(self.partes_diario()))

    def nombre_parte(self, parte: str) -> str:
        for c in self.consumo:
            if c["parte"] == parte:
                return c["lubricante"]
        for d in self.diario:
            if d["parte"] == parte:
                n = d.get("lubricante") or ""
                return n if "consumo diario" in n.lower() else f"{n} (consumo diario)"
        return ""

    def litros_pm(self, modelo: str, tipo, parte: str) -> float:
        if not es_num(tipo) or int(tipo) not in self.consumo_tipos:
            return 0.0
        k = str(int(tipo))
        return sum(float(c.get("litros") or 0) * float(c.get(k) or 0)
                   for c in self.consumo if c["modelo"] == modelo and c["parte"] == parte)

    def tasa_diaria(self, parte: str, equipo: str | None = None) -> float:
        return sum(float(d.get("litros_dia") or 0) for d in self.diario
                   if d["parte"] == parte and (equipo is None or d["equipo"] == equipo))

    # ------------------------------------------------- estado de un equipo (Calc)
    def estado(self, eq: str) -> dict:
        if eq in self._estado_cache:
            return self._estado_cache[eq]
        p, hoy = self.p, self.hoy
        filas = self.hist_eq.get(eq, [])
        n = len(filas)
        ult = filas[-1] if n else None
        lect = self.lecturas.get(eq) or {}
        horo_in = float(lect["horo"]) if es_num(lect.get("horo")) else None
        fecha_lect = lect.get("fecha")
        ult_tipo = float(ult["tipo"]) if ult and es_num(ult["tipo"]) else 0.0
        ult_horo = float(ult["horo"]) if ult and es_num(ult["horo"]) else 0.0
        ult_fecha = ult["fecha"] if ult else None
        mayores = [f for f in filas if f["tipo"] != 250]
        n_mayor = len(mayores)
        modelo = self.modelo_de(eq)
        largo, cierres, cfg_ciclo = self.ciclo_de(modelo)
        pos_last = (mayores[-1]["pos"] or 0) if n_mayor else 0
        pos_sig = pos_last % largo + 1
        sig_mayor = self.valor_ciclo(modelo, pos_sig)
        sugerido = 250.0 if n == 0 else (250.0 if ult_tipo != 250 else sig_mayor)
        posterior = 0.0 if n == 0 else (250.0 if sugerido != 250 else sig_mayor)
        s = 0 if sugerido == 250 else 1
        horo_hoy = horo_in if horo_in is not None else ult_horo
        intervalo = float(p["intervalo"])
        proyectado = ult_horo + intervalo
        acum = horo_hoy - ult_horo
        rest = proyectado - horo_hoy
        idx_base = n - int(p["pm_prom"])
        base = filas[idx_base - 1] if idx_base >= 1 else None
        horas_dia = float(p["horas_dia"])
        if base is None or ult_fecha is None or base["fecha"] is None:
            promedio = horas_dia
        else:
            dias = (ult_fecha - base["fecha"]).days
            promedio = max(1.0, (ult_horo - float(base["horo"] or 0)) / dias) if dias > 0 else horas_dia
        promedio_proy = promedio * (1 + float(p["avance_extra"]))
        fecha_proy = hoy + _d(redondear_arriba(max(0.0, rest) / promedio_proy))
        if n == 0:
            estado = "Sin historial: registre la última PM ejecutada"
        elif horo_in is None:
            estado = "Ingrese el horómetro de hoy"
        elif rest <= 0:
            estado = "Vencida"
        elif rest <= float(p["alerta_pm"]):
            estado = "Próxima"
        else:
            estado = "En plazo"
        pr = self.prog.get(eq) or {}
        fprog = None
        if n > 0 and pr and pr.get("fecha") and es_num(pr.get("tipo")) and es_num(pr.get("horo_obj")):
            if float(pr["tipo"]) == sugerido and float(pr["horo_obj"]) == proyectado:
                fprog = pr["fecha"]
        horo_en_prog = horo_hoy + max(0, (fprog - hoy).days) * promedio_proy if fprog else 0.0
        exceso = max(0.0, horo_en_prog - proyectado) if fprog else 0.0
        dias_rest = 0 if n == 0 else redondear_arriba(max(0.0, rest) / promedio_proy)
        margen_dias = redondear_arriba(dias_rest * float(p["margen_prog"]))
        fecha_sug = max(hoy, fecha_proy - _d(margen_dias))
        if n == 0:
            estado_prog = "SIN HISTORIAL"
        elif fprog is None:
            estado_prog = "NO PROGRAMADA"
        elif fprog < hoy:
            estado_prog = "PROGRAMACIÓN VENCIDA"
        elif fprog > fecha_sug:
            estado_prog = "PROGRAMADA CON RIESGO"
        else:
            estado_prog = "PROGRAMADA"
        detalle = {
            "SIN HISTORIAL": "Registre la última PM ejecutada del equipo para iniciar los cálculos.",
            "NO PROGRAMADA": "La PM pendiente no tiene fecha asignada. Programe idealmente hasta la fecha sugerida.",
            "PROGRAMACIÓN VENCIDA": "La fecha programada ya pasó y la PM no se ha registrado como ejecutada.",
            "PROGRAMADA": "Programada con margen de seguridad (hasta la fecha sugerida).",
        }.get(estado_prog)
        if estado_prog == "PROGRAMADA CON RIESGO":
            if fprog > fecha_proy:
                detalle = (f"Posterior al vencimiento proyectado: el equipo superaría el intervalo de "
                           f"{fmt_tipo(intervalo)} h en aprox. {int(redondear(exceso))} h.")
            else:
                detalle = (f"Dentro del margen de seguridad ({redondear(float(p['margen_prog']) * 100):.0f}%): "
                           "posterior a la fecha sugerida, pero anterior al vencimiento.")
        fecha_base = max(hoy, fprog if fprog else fecha_proy)
        fecha_post = fecha_base + _d(redondear(intervalo / promedio_proy))
        dias_lect = max(0, (hoy - (fecha_lect or hoy)).days)
        horo_est_hoy = ult_horo if horo_in is None else horo_in + promedio_proy * dias_lect
        horo_est_hoy_real = ult_horo if horo_in is None else horo_in + promedio * dias_lect
        fecha_av_pm = fprog if (fprog and fprog >= hoy) else fecha_sug
        horo_av_pm = horo_est_hoy + max(0, (fecha_av_pm - hoy).days) * promedio_proy
        horo_av_pm_real = horo_est_hoy_real + max(0, (fecha_av_pm - hoy).days) * promedio
        # Cumplimiento de la última PM
        if n == 0:
            cumplimiento = "-"
        elif not ult["fprog"]:
            cumplimiento = "Sin programación"
        elif ult_fecha is None:
            cumplimiento = "Sin fecha de ejecución"
        elif ult_fecha < ult["fprog"]:
            cumplimiento = f"Adelantada {(ult['fprog'] - ult_fecha).days} día(s)"
        elif ult_fecha == ult["fprog"]:
            cumplimiento = "En fecha"
        else:
            cumplimiento = f"Postergada {(ult_fecha - ult['fprog']).days} día(s)"
        # Alerta de horómetro (Panel P2)
        if horo_in is None:
            alerta = f"Sin lectura de horómetro para {eq}. Presione «Actualizar horómetro»."
        elif n > 0 and horo_in < ult_horo:
            alerta = f"Horómetro menor que el de la última PM ({fmt_tipo(ult_horo)} h). Actualice la lectura."
        elif fecha_lect is None or fecha_lect < hoy:
            alerta = ("Horómetro no actualizado hoy (última lectura: "
                      f"{fecha_lect.strftime('%d-%m-%Y') if fecha_lect else 'sin fecha'}).")
        else:
            alerta = ""
        e = dict(
            equipo=eq, modelo=modelo, faena=self.faena_de(eq), n=n, ult=ult, ult_tipo=ult_tipo,
            ult_horo=ult_horo, ult_fecha=ult_fecha, n_mayor=n_mayor, largo=largo, cierres=cierres,
            pos_last=pos_last, pos_sig=pos_sig, sig_mayor=sig_mayor, sugerido=sugerido, posterior=posterior,
            s=s, horo_in=horo_in, fecha_lect=fecha_lect, horo_hoy=horo_hoy, proyectado=proyectado,
            acum=acum, rest=rest, base=base, promedio=promedio, promedio_proy=promedio_proy,
            fecha_proy=fecha_proy, semana=f"S{semana_iso(fecha_proy):02d}", estado=estado, fprog=fprog,
            horo_en_prog=horo_en_prog, exceso=exceso, estado_prog=estado_prog, detalle_prog=detalle,
            horo_post=proyectado + intervalo, fecha_base=fecha_base, fecha_post=fecha_post,
            semana_post=f"S{semana_iso(fecha_post):02d}", dias_rest=dias_rest, margen_dias=margen_dias,
            fecha_sug=fecha_sug, horo_est_hoy=horo_est_hoy, horo_est_hoy_real=horo_est_hoy_real,
            av_sem=promedio * 7, av_mes=promedio * 30, fecha_av_pm=fecha_av_pm, horo_av_pm=horo_av_pm,
            horo_av_pm_real=horo_av_pm_real, cumplimiento=cumplimiento, alerta=alerta,
            con_lectura=horo_in is not None,
        )
        self._estado_cache[eq] = e
        return e

    # ----------------------------------------------------------- aceites (Panel)
    def ultimo_horo_aceite(self, eq: str, comp: str, hasta: float | None = None) -> float:
        m = 0.0
        for a in self.ac:
            if a["equipo"].strip() == eq and mismo_texto(a["comp"], comp):
                if a["origen"] != ORIGEN_NO and es_num(a["horo"]):
                    if (hasta is None or a["horo"] <= hasta) and a["horo"] > m:
                        m = float(a["horo"])
        return m

    def aceites_modelo(self, modelo: str) -> list[dict]:
        return [a for a in self.aceites_cfg if a["modelo"] == modelo]

    def control_aceites(self, eq: str) -> list[dict]:
        e = self.estado(eq)
        alerta = float(self.p["alerta_aceite"])
        out = []
        for a in self.aceites_modelo(e["modelo"]):
            freq = float(a["frecuencia"] or 0)
            if e["n"] == 0:
                ult = "-"
            else:
                u = self.ultimo_horo_aceite(eq, a["componente"])
                ult = u if u else "Sin registro"
            if es_num(ult):
                acum = e["horo_hoy"] - ult
                rest = freq - acum
                est = ("Cambio vencido" if acum >= freq else
                       "Cambio próximo" if acum >= freq * alerta else "En condiciones")
            else:
                acum = rest = est = "-"
            out.append(dict(componente=a["componente"], frecuencia=freq, ult=ult, acum=acum, rest=rest,
                            estado=est, texto=a["texto"]))
        return out

    # ------------------------------------------------------------ kits (Panel)
    def cuadros_kit(self) -> "OrderedDict[tuple, dict]":
        """Kits definidos en «Kits PM»: (modelo, tipo, cuadro) -> datos y líneas."""
        cuadros: OrderedDict = OrderedDict()
        for k in self.kits:
            clave = (k["modelo"], float(k["tipo"] or 0), int(k["cuadro"] or 1))
            c = cuadros.setdefault(clave, dict(modelo=k["modelo"], tipo=float(k["tipo"] or 0),
                                               cuadro=int(k["cuadro"] or 1), kit=k["kit"],
                                               ubic_kit=k["ubic_kit"], equipos_txt=k["equipos"], lineas=[]))
            c["lineas"].append(k)
        for c in cuadros.values():
            c["lineas"].sort(key=lambda x: x["linea"])
            txt = c["equipos_txt"].replace("(tabla resumen)", "").strip()
            c["equipos_limpio"] = txt
            c["equipos"] = [x.strip() for x in txt.split("-") if x.strip()]
        return cuadros

    def kits_de(self, modelo: str, tipo: float) -> list[dict]:
        return [c for (m, t, _), c in self.cuadros_kit().items() if m == modelo and t == float(tipo)]

    # ------------------------------------------------------ proyección de PM
    def proyeccion(self, eq: str, n: int = N_PROY_EQUIPO) -> list[dict]:
        clave = (eq, n)
        if clave in self._proy_cache:
            return self._proy_cache[clave]
        e = self.estado(eq)
        out = []
        if e["n"] > 0:
            intervalo = float(self.p["intervalo"])
            partes = self.partes_pm()
            for k in range(1, n + 1):
                if (k + e["s"]) % 2 == 1:
                    tipo = 250.0
                else:
                    pos = (e["pos_sig"] - 1 + (k + e["s"]) // 2 - 1) % e["largo"] + 1
                    tipo = self.valor_ciclo(e["modelo"], pos)
                horo = e["proyectado"] + (k - 1) * intervalo
                fecha = e["fecha_base"] + _d(redondear((k - 1) * intervalo / e["promedio_proy"]))
                litros = {pt: self.litros_pm(e["modelo"], tipo, pt) for pt in partes}
                out.append(dict(k=k, equipo=eq, modelo=e["modelo"], tipo=tipo, horo=horo, fecha=fecha,
                                mes=fecha.replace(day=1), litros=litros,
                                etiqueta=f"PM {fmt_tipo(tipo)} · {etiqueta_corta(fecha)}"))
        self._proy_cache[clave] = out
        return out

    def proyeccion_flota(self) -> list[dict]:
        out = []
        for eq in self.lista_equipos():
            out.extend(self.proyeccion(eq))
        return out

    def resumen_meses(self, eq: str, meses: int = 6) -> dict:
        """Hoja Proyección y franja «Proyección 6 meses» del Panel."""
        modelo = self.modelo_de(eq)
        tipos = [250, 500, 1000, 2000 if modelo == "DR412i" else self.tipo_cierre(modelo)]
        pr = self.proyeccion(eq, N_PROY_PANEL)
        filas = []
        for i in range(meses):
            mes = primer_dia_mes(self.hoy, i)
            de_mes = [x for x in pr if x["mes"] == mes]
            cuenta = [sum(1 for x in de_mes if x["tipo"] == t) for t in tipos]
            det = ", ".join(f"PM {fmt_tipo(x['tipo'])} ({x['fecha'].day:02d}-{x['fecha'].month:02d})" for x in de_mes)
            filas.append(dict(mes=mes, cuenta=cuenta, total=sum(cuenta), detalle=det if sum(cuenta) else "Sin PM"))
        tot = [sum(f["cuenta"][j] for f in filas) for j in range(len(tipos))]
        return dict(tipos=tipos, filas=filas, total=tot, proyeccion=pr)

    # ------------------------------------------- historial: utilidades
    def ejecutadas_en(self, ini: dt.date, fin: dt.date, equipo: str | None = None) -> list[dict]:
        return [f for f in self.hist if f["fecha"] and ini <= f["fecha"] <= fin
                and (equipo is None or f["equipo"].strip() == equipo)]

    # ------------------------------------------------- proyección de aceites
    def periodo(self, desde: dt.date | None, hasta: dt.date | None) -> dict:
        hoy = self.hoy
        ini = desde or hoy
        fin = max(hasta or ini, ini)
        fin_ej = min(fin, hoy)
        dias = (fin - ini).days + 1
        dias_ej = max(0, (min(fin, hoy) - ini).days + 1)
        dias_pr = max(0, (fin - max(ini, hoy + DIA)).days + 1)
        partes = self.partes()
        pm_partes = set(self.partes_pm())
        tipos_ok = set(self.consumo_tipos)
        eqs = self.lista_equipos()
        ejec = {eq: defaultdict(float) for eq in eqs}
        proy = {eq: defaultdict(float) for eq in eqs}
        n_ej, n_ej_all, n_pr = {}, {}, {}
        for eq in eqs:
            modelo = self.modelo_de(eq)
            filas = self.ejecutadas_en(ini, fin_ej, eq)
            n_ej_all[eq] = len(filas)
            n_ej[eq] = 0
            for f in filas:
                if es_num(f["tipo"]) and int(f["tipo"]) in tipos_ok:
                    n_ej[eq] += 1
                    for pt in pm_partes:
                        ejec[eq][pt] += self.litros_pm(modelo, f["tipo"], pt)
            for pt in self.partes_diario():
                ejec[eq][pt] += dias_ej * self.tasa_diaria(pt, eq)
                proy[eq][pt] += dias_pr * self.tasa_diaria(pt, eq)
            pr = [x for x in self.proyeccion(eq) if ini <= x["fecha"] <= fin]
            n_pr[eq] = len(pr)
            for x in pr:
                for pt, l in x["litros"].items():
                    proy[eq][pt] += l
        margen, tarro = float(self.p["margen"]), float(self.p["tarro"])
        filas = []
        for pt in partes:
            por_eq = [ejec[eq][pt] + proy[eq][pt] for eq in eqs]
            e_ = sum(ejec[eq][pt] for eq in eqs)
            p_ = sum(proy[eq][pt] for eq in eqs)
            tot = e_ + p_
            conm = tot + tot * margen
            tarros = redondear_arriba(conm / tarro) if tarro else 0
            filas.append(dict(parte=pt, nombre=self.nombre_parte(pt), por_eq=por_eq, ejec=e_, proy=p_,
                              total=tot, margen=tot * margen, con_margen=conm, tarros=tarros,
                              sobrante=tarros * tarro - conm))
        # Sección 3: por año
        anos = []
        n_anos = min(10, fin.year - ini.year + 1)
        tasa_total = {pt: self.tasa_diaria(pt) for pt in self.partes_diario()}
        flota = self.proyeccion_flota()
        for i in range(n_anos):
            a = ini.year + i
            c = max(ini, dt.date(a, 1, 1))
            d = min(fin, dt.date(a, 12, 31))
            e = min(d, hoy)
            f_ = max(0, (e - c).days + 1)
            g_ = max(0, (d - max(c, hoy + DIA)).days + 1)
            ej_rows = [x for x in self.hist if x["fecha"] and c <= x["fecha"] <= e]
            pr_rows = [x for x in flota if c <= x["fecha"] <= d]
            lit = {}
            for pt in partes:
                v = 0.0
                if pt in pm_partes:
                    for x in ej_rows:
                        eq = x["equipo"].strip()
                        if eq in eqs:
                            v += self.litros_pm(self.modelo_de(eq), x["tipo"], pt)
                    v += sum(x["litros"].get(pt, 0.0) for x in pr_rows)
                if pt in tasa_total:
                    v += (f_ + g_) * tasa_total[pt]
                lit[pt] = v
            anos.append(dict(ano=a, n_ej=len(ej_rows), n_pr=len(pr_rows), litros=lit, total=sum(lit.values())))
        # Sección 4: por equipo
        por_equipo = []
        for eq in eqs:
            e = self.estado(eq)
            pr = self.proyeccion(eq)
            por_equipo.append(dict(equipo=eq, modelo=e["modelo"], horo_hoy=e["horo_hoy"],
                                   pm_actual=e["sugerido"], n_ej=n_ej_all[eq], n_pr=n_pr[eq],
                                   tasa=self.tasa_diaria("LL-0006", eq) if "LL-0006" in self.partes_diario()
                                   else sum(self.tasa_diaria(pt, eq) for pt in self.partes_diario()),
                                   cubre=pr[-1]["fecha"] if pr else None))
        # Sección 5: por modelo
        modelos = list(OrderedDict.fromkeys(self.modelo_de(eq) for eq in eqs))
        por_modelo = []
        for m in modelos:
            eqm = [eq for eq in eqs if self.modelo_de(eq) == m]
            lit = {pt: sum(ejec[eq][pt] + proy[eq][pt] for eq in eqm) for pt in partes}
            conm = {pt: v * (1 + margen) for pt, v in lit.items()}
            por_modelo.append(dict(modelo=m, equipos=eqm, litros=lit, con_margen=conm,
                                   tarros={pt: redondear_arriba(v / tarro) for pt, v in conm.items()},
                                   n_pm=sum(n_ej_all[eq] + n_pr[eq] for eq in eqm)))
        n_pm = [n_ej_all[eq] + n_pr[eq] for eq in eqs]
        return dict(ini=ini, fin=fin, fin_ej=fin_ej, dias=dias, dias_ej=dias_ej, dias_pr=dias_pr,
                    equipos=eqs, partes=partes, filas=filas, n_pm=n_pm,
                    n_ej_total=sum(n_ej_all.values()), n_pr_total=sum(n_pr.values()),
                    anos=anos, por_equipo=por_equipo, por_modelo=por_modelo,
                    total_con_margen=sum(f["con_margen"] for f in filas),
                    total_tarros=sum(f["tarros"] for f in filas))

    def texto_tramos(self, d1: dt.date, d2: dt.date) -> str:
        hoy, t = self.hoy, ""
        f = lambda d: d.strftime("%d-%m-%Y")  # noqa: E731
        if d1 <= hoy:
            t = f"Ejecutado (Historial): {f(d1)} al {f(min(d2, hoy))}"
        if d2 >= hoy:
            t += ("  ·  " if t else "") + f"Proyectado: {f(max(d1, hoy))} al {f(d2)}"
        return t

    # ---------------------------------------------------- aceites por semanas
    def semanas(self, ini: dt.date | None, n_sem) -> dict:
        hoy = self.hoy
        ini = ini or hoy
        n = max(1, min(SEM_MAX, int(n_sem))) if es_num(n_sem) else 4
        fin = ini + _d(7 * n - 1)
        ini_p = max(ini, hoy)
        fin_ej = min(fin, hoy)
        dias = (fin - ini).days + 1
        eqs = self.lista_equipos()
        partes = self.partes()
        pm_partes = self.partes_pm()
        tipos_ok = set(self.consumo_tipos)
        # PM proyectadas en el plazo
        proy = []
        for x in self.proyeccion_flota():
            if ini_p <= x["fecha"] <= fin:
                proy.append(dict(x, sem=(x["fecha"] - ini).days // 7 + 1))
        # PM ejecutadas por semana y equipo (bloques de CalcFlota)
        ejec = {}
        for w in range(1, n + 1):
            a = ini + _d(7 * (w - 1))
            b = min(ini + _d(7 * w - 1), fin_ej)
            for eq in eqs:
                modelo = self.modelo_de(eq)
                filas = [] if b < a else [f for f in self.ejecutadas_en(a, b, eq)
                                          if es_num(f["tipo"]) and int(f["tipo"]) in tipos_ok]
                lit = {pt: sum(self.litros_pm(modelo, f["tipo"], pt) for f in filas) for pt in pm_partes}
                etiqueta = ""
                if filas:
                    f1 = min(f["fecha"] for f in filas)
                    t1 = min(float(f["tipo"]) for f in self.hist_eq.get(eq, []) if f["fecha"] == f1 and es_num(f["tipo"]))
                    etiqueta = (f"PM {fmt_tipo(t1)} · {etiqueta_corta(f1)} (ejec.)"
                                + (f" (+{len(filas) - 1})" if len(filas) > 1 else ""))
                ejec[(eq, w)] = dict(n=len(filas), litros=lit, etiqueta=etiqueta)
        # Sección 2: por equipo
        filas = []
        margen, tarro = float(self.p["margen"]), float(self.p["tarro"])
        for pt in partes:
            por_eq = []
            for eq in eqs:
                v = sum(x["litros"].get(pt, 0.0) for x in proy if x["equipo"] == eq)
                v += sum(ejec[(eq, w)]["litros"].get(pt, 0.0) for w in range(1, n + 1))
                v += self.tasa_diaria(pt, eq) * dias
                por_eq.append(v)
            tot = sum(por_eq)
            conm = tot + tot * margen
            tarros = redondear_arriba(conm / tarro) if tarro else 0
            filas.append(dict(parte=pt, nombre=self.nombre_parte(pt), por_eq=por_eq, total=tot,
                              margen=tot * margen, con_margen=conm, tarros=tarros, sobrante=tarros * tarro - conm))
        n_pm = [sum(1 for x in proy if x["equipo"] == eq) + sum(ejec[(eq, w)]["n"] for w in range(1, n + 1))
                for eq in eqs]
        # Sección 3: semana a semana
        tasa_total = {pt: self.tasa_diaria(pt) for pt in partes}
        semanas = []
        for w in range(1, n + 1):
            a = ini + _d(7 * (w - 1))
            b = ini + _d(7 * w - 1)
            iso_a, iso_b = semana_iso(a), semana_iso(b)
            celdas = []
            for eq in eqs:
                de_sem = [x for x in proy if x["equipo"] == eq and x["sem"] == w]
                f_txt = (de_sem[0]["etiqueta"] + (f" (+{len(de_sem) - 1})" if len(de_sem) > 1 else "")) if de_sem else ""
                e_txt = ejec[(eq, w)]["etiqueta"]
                celdas.append((f_txt or "–") if not e_txt else (e_txt if not f_txt else f"{e_txt} / {f_txt}"))
            n_w = sum(1 for x in proy if x["sem"] == w) + sum(ejec[(eq, w)]["n"] for eq in eqs)
            dias_w = max(0, (min(b, fin) - max(a, ini)).days + 1)
            lit = {}
            for pt in partes:
                v = sum(x["litros"].get(pt, 0.0) for x in proy if x["sem"] == w)
                v += sum(ejec[(eq, w)]["litros"].get(pt, 0.0) for eq in eqs)
                v += tasa_total[pt] * dias_w
                lit[pt] = v
            semanas.append(dict(sem=w, ini=a, fin=b,
                                periodo=f"{a.day:02d}-{a.month:02d} al {b.day:02d}-{b.month:02d}-{b.year}",
                                iso=f"S{iso_a:02d}" + (f"-{iso_b:02d}" if iso_b != iso_a else ""),
                                celdas=celdas, n_pm=n_w, litros=lit, total=sum(lit.values())))
        return dict(ini=ini, n=n, fin=fin, ini_p=ini_p, fin_ej=fin_ej, dias=dias, equipos=eqs, partes=partes,
                    filas=filas, n_pm=n_pm, n_pm_total=sum(n_pm), semanas=semanas, proyectadas=proy,
                    total_con_margen=sum(f["con_margen"] for f in filas),
                    total_tarros=sum(f["tarros"] for f in filas))

    # --------------------------------------------------------- kits a solicitar
    def kits_solicitar(self, per: dict, sem: dict) -> dict:
        cuadros = self.cuadros_kit()
        filas = []
        for (modelo, tipo, cuadro), c in cuadros.items():
            n_per = sum(1 for eq in c["equipos"] for x in self.proyeccion(eq)
                        if x["tipo"] == tipo and per["ini"] <= x["fecha"] <= per["fin"])
            n_sem = sum(1 for x in sem["proyectadas"] if x["equipo"] in c["equipos"] and x["tipo"] == tipo)
            n_sem += sum(1 for eq in c["equipos"] for f in self.ejecutadas_en(sem["ini"], sem["fin_ej"], eq)
                         if f["tipo"] == tipo)
            filas.append(dict(clave=(modelo, tipo, cuadro), kit=c["kit"],
                              etiqueta=f"{modelo} · PM {fmt_tipo(tipo)}", equipos=" - ".join(c["equipos"]),
                              ubic=c["ubic_kit"], n_per=n_per, n_sem=n_sem))
        # Repuestos sueltos (líneas ADIC)
        rep: OrderedDict = OrderedDict()
        mt = defaultdict(int)
        for (m, t, _) in cuadros:
            mt[(m, t)] += 1
        for f in filas:
            c = cuadros[f["clave"]]
            cat = "suelto"
            for ln in c["lineas"]:
                tl = ln["tipo_linea"]
                if tl == "SUB":
                    cat = "kit" if ln["linea"] == 1 else categoria_suelto(ln["com"])
                elif tl == "ADIC" and ln["np"]:
                    r = rep.setdefault(ln["np"], dict(np=ln["np"], ubic="", origen=OrderedDict(), n_per=0.0, n_sem=0.0))
                    q = float(ln["cant"] or 0)
                    if ln["ubic"] and ln["ubic"] != "-" and not r["ubic"]:
                        r["ubic"] = ln["ubic"]
                    et = f"{c['modelo']} PM {fmt_tipo(c['tipo'])}"
                    if mt[(c["modelo"], c["tipo"])] > 1:
                        et += f" ({' - '.join(c['equipos'])})"
                    clave_o = (et, cat)
                    r["origen"][clave_o] = r["origen"].get(clave_o, 0.0) + q
                    r["n_per"] += f["n_per"] * q
                    r["n_sem"] += f["n_sem"] * q
        repuestos = []
        for r in rep.values():
            orig = "; ".join(f"{et} · {cat} · {fmt_tipo(q)} c/u" for (et, cat), q in r["origen"].items())
            repuestos.append(dict(np=r["np"], ubic=r["ubic"], origen=orig, n_per=r["n_per"], n_sem=r["n_sem"]))
        return dict(kits=filas, repuestos=repuestos)
