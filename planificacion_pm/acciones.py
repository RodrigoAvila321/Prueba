"""Acciones del usuario: traducción de las macros VBA (módulo ModPlanificacionPM).
La interfaz se inyecta como `ui` para poder usar la misma lógica en ventanas o en pruebas."""
from __future__ import annotations

import datetime as dt
import getpass
from typing import Protocol

from .motor import MESES_MAX, SEM_MAX, Motor
from .util import (ORIGEN_FUERA, ORIGEN_IND, ORIGEN_NO, ORIGEN_PM, SIN_ANTERIOR, es_num, fmt_fecha,
                   fmt_num, fmt_pct, fmt_tipo, mismo_texto, parse_fecha, parse_num, sumar_meses)


class UI(Protocol):
    def info(self, msg: str) -> None: ...
    def aviso(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def si_no(self, msg: str, defecto_no: bool = False, icono: str = "question") -> bool: ...
    def si_no_cancelar(self, msg: str) -> bool | None: ...
    def pedir(self, msg: str, titulo: str = "", defecto: str = "") -> str | None: ...
    def elegir_varios(self, msg: str, opciones: list[str]) -> list[int] | None: ...


class Acciones:
    def __init__(self, motor: Motor, ui: UI):
        self.m = motor
        self.repo = motor.repo
        self.ui = ui

    # ---------------------------------------------------------------- utilidades
    def usuario(self) -> str:
        u = str(self.m.p.get("usuario") or "").strip()
        if u:
            return u
        try:
            return getpass.getuser()
        except Exception:  # pragma: no cover
            return "Usuario"

    def recargar(self):
        self.m.recargar()

    def equipo_valido(self, eq: str) -> bool:
        if not eq or eq not in self.m.lista_equipos():
            self.ui.aviso("Seleccione un equipo válido de la lista.")
            return False
        return True

    def escribir_programacion(self, eq: str, tipo: float, horo_obj: float, fecha: dt.date | None):
        if tipo == 0:
            self.repo.set_programacion(eq, None, None, None, dt.datetime.now())
        else:
            self.repo.set_programacion(eq, tipo, horo_obj, fecha, dt.datetime.now())

    # ------------------------------------------------------- posición en el ciclo
    @staticmethod
    def posicion_ciclo(tipo: float, ult_pos: int, largo: int, cierres: str) -> int:
        largo = max(1, largo)
        if f",{fmt_tipo(tipo)}," in f",{cierres},":
            return largo
        return ult_pos % largo + 1

    def pos_nueva(self, eq: str, tipo: float) -> int | None:
        if tipo == 250:
            return None
        ult_pos = 0
        for f in self.m.hist_eq.get(eq, []):
            if es_num(f["tipo"]) and f["tipo"] != 250 and f["pos"] is not None:
                ult_pos = int(f["pos"])
        largo, cierres, _ = self.m.ciclo_de(self.m.modelo_de(eq))
        return self.posicion_ciclo(tipo, ult_pos, largo, cierres)

    def reparar_claves(self, silencioso: bool = False) -> int:
        """RepararClaves: recalcula la posición en el ciclo de todas las PM mayores."""
        ult: dict[str, int] = {}
        n = 0
        with self.repo.transaccion():
            for f in self.repo.historial():
                eq = f["equipo"].strip()
                if es_num(f["tipo"]) and f["tipo"] != 250:
                    largo, cierres, _ = self.m.ciclo_de(self.m.modelo_de(eq))
                    ult[eq] = self.posicion_ciclo(float(f["tipo"]), ult.get(eq, 0), largo, cierres)
                    nuevo = ult[eq]
                else:
                    nuevo = None
                if f["pos"] != nuevo:
                    self.repo.actualizar_historial(f["seq"], {"pos": nuevo})
                    n += 1
        self.recargar()
        if not silencioso:
            self.ui.info(f"Claves del Historial recalculadas correctamente ({n} fila(s) corregida(s)).")
        return n

    # ------------------------------------------------------------- horómetro
    def actualizar_horometro(self, eq: str, al_abrir: bool = False) -> bool:
        if not self.equipo_valido(eq):
            return False
        e = self.m.estado(eq)
        lect = self.m.lecturas.get(eq) or {}
        ult_lect, f_lect = lect.get("horo"), lect.get("fecha")
        txt = f"Equipo: {eq}\n"
        txt += (f"Última PM: PM {fmt_tipo(e['ult_tipo'])} a {fmt_num(e['ult_horo'])} h\n" if e["n"] > 0
                else "Última PM: sin registros\n")
        if es_num(ult_lect):
            txt += f"Última lectura: {fmt_num(ult_lect)} h" + (f" ({fmt_fecha(f_lect)})" if f_lect else "")
        else:
            txt += "Última lectura: sin registro"
        while True:
            s = self.ui.pedir(f"{txt}\n\nIngrese el horómetro de HOY del equipo {eq}:",
                              "Horómetro de hoy", "")
            if not s or not s.strip():
                if al_abrir:
                    self.ui.aviso("No se ingresó el horómetro.\n"
                                  "El Panel mostrará una alerta hasta que lo actualice con «Actualizar horómetro».")
                return False
            v = parse_num(s)
            if v is None:
                self.ui.aviso("Ingrese un valor numérico (sin unidades).")
            elif v <= 0:
                self.ui.aviso("El horómetro debe ser mayor que cero.")
            elif e["n"] > 0 and v < e["ult_horo"]:
                self.ui.aviso(f"El horómetro no puede ser menor que el de la última PM ({fmt_num(e['ult_horo'])} h).")
            else:
                if es_num(ult_lect) and v < ult_lect:
                    if not self.ui.si_no(f"El valor ingresado ({fmt_num(v)} h) es menor que la última lectura "
                                         f"({fmt_num(ult_lect)} h).\n\n¿Es correcto?", defecto_no=True,
                                         icono="warning"):
                        continue
                break
        with self.repo.transaccion():
            self.repo.set_lectura(eq, v, self.m.hoy, self.usuario())
        self.recargar()
        if not al_abrir:
            self.ui.info(f"Horómetro del equipo {eq} actualizado: {fmt_num(v)} h.")
        return True

    # -------------------------------------------------------- fechas futuras
    def limpiar_fechas_futuras(self, eq: str = "", desde_registro: bool = False) -> int:
        hoy = self.m.hoy
        filas = [f for f in self.repo.historial()
                 if (not eq or f["equipo"].strip() == eq) and f["fecha"] and f["fecha"] > hoy]
        if not filas:
            return 0
        lista = "".join(f"\n- {f['equipo']}  PM {fmt_tipo(f['tipo'])} a {fmt_num(f['horo'])} h, fecha "
                        f"{fmt_fecha(f['fecha'])}" for f in filas)
        msg = (f"Se encontraron PM ejecutadas con fecha posterior a hoy ({fmt_fecha(hoy)}):\n{lista}\n\n"
               "¿Desea eliminar esas fechas? La PM se conserva y queda una nota en Observación.")
        if desde_registro:
            msg += "\n(Si responde No, la fecha igual no bloqueará el registro.)"
        if not self.ui.si_no(msg):
            return 0
        with self.repo.transaccion():
            for f in filas:
                nota = f"Fecha original {fmt_fecha(f['fecha'])} eliminada (posterior a la fecha de revisión)"
                obs = (f["obs"] or "").strip()
                self.repo.actualizar_historial(f["seq"], {"fecha": None, "obs": nota if not obs else f"{obs}; {nota}"})
        self.recargar()
        self.ui.info(f"{len(filas)} fecha(s) eliminada(s). Ya puede registrar la PM con la fecha de hoy.")
        return len(filas)

    def corregir_fechas_futuras(self):
        if self.limpiar_fechas_futuras("", False) == 0:
            self.ui.info("No hay PM con fecha de ejecución posterior a hoy en el Historial.")

    # ------------------------------------------------------------ dar ejecutada
    def _pedir_horo_aceite(self, comp: str, ult_cambio, limite: float, defecto: str) -> float | None:
        if es_num(ult_cambio):
            minimo = float(ult_cambio)
            txt_min = f"mayor que {fmt_num(minimo)} h (cambio anterior) y "
        else:
            minimo = 0.0
            txt_min = "mayor que 0 y "
        while True:
            s = self.ui.pedir(f"Ingrese el horómetro en que se cambió «{comp}».\n\n"
                              f"Debe ser {txt_min}no mayor que {fmt_num(limite)} h.\n\n"
                              "Deje vacío si aún no se ha cambiado.", "Horómetro del cambio", defecto)
            if not s or not s.strip():
                return None
            v = parse_num(s)
            if v is None:
                self.ui.aviso("Ingrese un valor numérico (sin unidades).")
            elif v <= minimo or v > limite:
                self.ui.aviso(f"El horómetro debe ser {txt_min}no mayor que {fmt_num(limite)} h.")
            else:
                return v

    def dar_ejecutada(self, eq: str, v_tipo, v_fecha, v_horo, obs: str = "") -> bool:
        """Botón «Dar ejecutada». Devuelve True si se registró la PM."""
        m, ui = self.m, self.ui
        if not self.equipo_valido(eq):
            return False
        self.limpiar_fechas_futuras(eq, True)
        e = m.estado(eq)
        obs = (obs or "").strip()
        tipo = parse_num(v_tipo) if v_tipo not in (None, "") else None
        if tipo is None:
            ui.aviso("Seleccione el tipo de PM ejecutada.")
            return False
        if int(tipo) not in m.tipos_validos(e["modelo"]):
            ui.aviso(f"El tipo de PM {fmt_tipo(tipo)} no es válido. Seleccione uno de la lista.")
            return False
        fecha = v_fecha if isinstance(v_fecha, dt.date) else parse_fecha(v_fecha or "")
        if fecha is None:
            ui.aviso("Ingrese una fecha de ejecución válida.")
            return False
        if fecha > m.hoy:
            ui.aviso("La fecha de ejecución no puede ser posterior a hoy.")
            return False
        horo = parse_num(v_horo) if v_horo not in (None, "") else None
        if horo is None:
            ui.aviso("Ingrese el horómetro de ejecución de la PM.")
            return False
        if horo <= 0:
            ui.aviso("El horómetro de ejecución debe ser mayor que cero.")
            return False
        limite = horo
        if e["horo_in"] is not None:
            if horo > e["horo_in"]:
                ui.aviso(f"El horómetro de ejecución ({fmt_num(horo)} h) no puede ser mayor que el horómetro "
                         f"de hoy ({fmt_num(e['horo_in'])} h).")
                return False
            limite = e["horo_in"]
        filas_eq = m.hist_eq.get(eq, [])
        if filas_eq:
            max_horo = max(float(f["horo"]) for f in filas_eq if es_num(f["horo"]))
            fechas = [f["fecha"] for f in filas_eq if f["fecha"] and f["fecha"] <= m.hoy]
            max_fecha = max(fechas) if fechas else None
            if horo <= max_horo:
                ui.aviso(f"Ya existe una PM del equipo {eq} registrada con horómetro {fmt_num(max_horo)} h. "
                         "El horómetro de ejecución debe ser mayor.")
                return False
            if max_fecha and fecha < max_fecha:
                ui.aviso(f"La fecha de ejecución no puede ser anterior a la última PM registrada "
                         f"({fmt_fecha(max_fecha)}).")
                return False
            if tipo != e["sugerido"]:
                if not ui.si_no(f"Según el ciclo, la PM que corresponde es la PM {fmt_tipo(e['sugerido'])}.\n"
                                f"Usted seleccionó PM {fmt_tipo(tipo)}.\n\n"
                                f"¿Desea registrar la PM {fmt_tipo(tipo)} de todas formas?", defecto_no=True,
                                icono="warning"):
                    return False

        # ---- Confirmación de aceites, uno por uno
        aceites = m.control_aceites(eq)
        n_ac = len(aceites)
        origen: dict[int, str] = {}
        horo_ac: dict[int, float] = {}
        otros = []
        for j, a in enumerate(aceites):
            if tipo >= a["frecuencia"]:
                resp = ui.si_no_cancelar(
                    f"Aceite {j + 1} de {n_ac}: «{a['componente']}»\n\n"
                    f"¿Se cambió en esta PM {fmt_tipo(tipo)} (horómetro {fmt_num(horo)} h)?\n\n"
                    "Sí: cambiado en la PM.\nNo: indicar otro horómetro o «no cambiado aún».\n"
                    "Cancelar: anular el registro de la PM.")
                if resp is None:
                    ui.info("Registro anulado. No se guardó ningún dato.")
                    return False
                if resp:
                    origen[j], horo_ac[j] = ORIGEN_PM, horo
                else:
                    v = self._pedir_horo_aceite(a["componente"], a["ult"], limite, "")
                    if v is not None:
                        horo_ac[j] = v
                        origen[j] = ORIGEN_PM if v == horo else ORIGEN_FUERA
                    else:
                        origen[j], horo_ac[j] = ORIGEN_NO, 0.0
            else:
                otros.append(j)
        if otros:
            lista = "".join(f"\n- {aceites[j]['componente']}" for j in otros)
            if ui.si_no(f"Los siguientes aceites no correspondían a la PM {fmt_tipo(tipo)}:\n{lista}\n\n"
                        "¿Alguno de ellos se cambió de todas formas?", defecto_no=True):
                for j in otros:
                    if ui.si_no(f"¿Se cambió «{aceites[j]['componente']}»?", defecto_no=True):
                        v = self._pedir_horo_aceite(aceites[j]["componente"], aceites[j]["ult"], limite,
                                                    fmt_tipo(horo))
                        if v is not None:
                            horo_ac[j] = v
                            origen[j] = ORIGEN_PM if v == horo else ORIGEN_FUERA

        # ---- Confirmación final
        fprog = e["fprog"]
        horas_ac: dict[int, object] = {}
        for j, o in origen.items():
            if o in (ORIGEN_PM, ORIGEN_FUERA):
                prev = m.ultimo_horo_aceite(eq, aceites[j]["componente"])
                horas_ac[j] = horo_ac[j] - prev if prev > 0 else SIN_ANTERIOR
        res = (f"Equipo: {eq}   |   PM {fmt_tipo(tipo)}\nFecha: {fmt_fecha(fecha)}   |   Horómetro: {fmt_num(horo)} h\n"
               f"Programación: {fmt_fecha(fprog) if fprog else 'No programada'}\n\nAceites:")
        for j in sorted(origen):
            comp = aceites[j]["componente"]
            if origen[j] == ORIGEN_PM:
                res += f"\n- {comp}: cambiado en la PM{_texto_horas(horas_ac.get(j))}"
            elif origen[j] == ORIGEN_FUERA:
                res += f"\n- {comp}: cambiado a {fmt_num(horo_ac[j])} h{_texto_horas(horas_ac.get(j))}"
            else:
                res += f"\n- {comp}: no cambiado aún"
        if obs:
            res += f"\n\nObservación: {obs}"
        if not ui.si_no(f"¿Confirma dar por EJECUTADA la siguiente PM?\n\n{res}"):
            return False

        # ---- Escritura
        nuevo_id = max((int(f["id"]) for f in m.hist), default=0) + 1
        ahora = dt.datetime.now().replace(microsecond=0)
        with self.repo.transaccion():
            self.repo.agregar_historial({
                "id": nuevo_id, "equipo": eq, "modelo": m.modelo_de(eq), "faena": m.faena_de(eq), "tipo": tipo,
                "fecha": fecha, "horo": horo, "horas": horo - e["ult_horo"] if e["n"] > 0 else None,
                "fprog": fprog, "obs": obs, "reg_el": ahora, "reg_por": self.usuario(),
                "pos": self.pos_nueva(eq, tipo)})
            for j in sorted(origen):
                self.repo.agregar_aceite({
                    "id_pm": nuevo_id, "equipo": eq, "comp": aceites[j]["componente"],
                    "horo": None if origen[j] == ORIGEN_NO else horo_ac[j], "origen": origen[j],
                    "reg_el": ahora, "horas_ac": horas_ac.get(j)})
            self.escribir_programacion(eq, 0, 0, None)
        self.recargar()
        e2 = m.estado(eq)
        ui.info(f"PM {fmt_tipo(tipo)} del equipo {eq} dada por EJECUTADA.\n"
                f"Cumplimiento: {e2['cumplimiento']}\n"
                f"Próxima PM: PM {fmt_tipo(e2['sugerido'])} a las {fmt_num(e2['proyectado'])} h (sin programar).")
        return True

    # -------------------------------------------------------------- programar
    def programar_pm(self, eq: str, v_fecha) -> bool:
        m, ui = self.m, self.ui
        if not self.equipo_valido(eq):
            return False
        e = m.estado(eq)
        if e["n"] == 0:
            ui.aviso(f"El equipo {eq} no tiene PM registradas.\n"
                     "Registre primero su última PM ejecutada para conocer la PM pendiente.")
            return False
        sug, proy, f_act = e["sugerido"], e["proyectado"], e["fprog"]
        if v_fecha in (None, "") or (isinstance(v_fecha, str) and not v_fecha.strip()):
            if not f_act:
                ui.aviso(f"Ingrese la fecha programada para la PM {fmt_tipo(sug)} del equipo {eq}.")
                return False
            if not ui.si_no(f"¿Desea anular la programación de la PM {fmt_tipo(sug)} del equipo {eq} "
                            f"(fecha {fmt_fecha(f_act)})?", defecto_no=True):
                return False
            with self.repo.transaccion():
                self.escribir_programacion(eq, 0, 0, None)
            self.recargar()
            ui.info(f"Programación anulada. La PM {fmt_tipo(sug)} queda como NO PROGRAMADA.")
            return True
        fp = v_fecha if isinstance(v_fecha, dt.date) else parse_fecha(v_fecha)
        if fp is None:
            ui.aviso("Ingrese una fecha programada válida (dd-mm-aaaa).")
            return False
        if fp < m.hoy:
            ui.aviso("La fecha programada no puede ser anterior a hoy.")
            return False
        if e["horo_in"] is not None:
            pct = fmt_pct(m.p["margen_prog"])
            if fp > e["fecha_proy"]:
                exceso = max(0.0, e["horo_in"] + (fp - m.hoy).days * e["promedio_proy"] - proy)
                if not ui.si_no(
                        f"ADVERTENCIA: la fecha programada ({fmt_fecha(fp)}) es posterior al vencimiento proyectado "
                        f"({fmt_fecha(e['fecha_proy'])}).\nCon el avance proyectado de {fmt_num(e['promedio_proy'], 1)} "
                        f"h/día (promedio real + {fmt_pct(m.p['avance_extra'])}), el equipo superaría el intervalo "
                        f"en aprox. {fmt_num(exceso)} h.\n\nFecha sugerida para programar: {fmt_fecha(e['fecha_sug'])} "
                        f"(margen de seguridad {pct}).\n\n¿Desea programar en esa fecha de todas formas?",
                        defecto_no=True, icono="warning"):
                    return False
            elif fp > e["fecha_sug"]:
                if not ui.si_no(
                        f"ADVERTENCIA: la fecha programada ({fmt_fecha(fp)}) queda dentro del margen de seguridad "
                        f"({pct}).\nEs anterior al vencimiento proyectado ({fmt_fecha(e['fecha_proy'])}), pero "
                        f"posterior a la fecha sugerida ({fmt_fecha(e['fecha_sug'])}).\n\nLa PM quedará como "
                        "«PROGRAMADA CON RIESGO». ¿Desea programar en esa fecha de todas formas?",
                        defecto_no=True, icono="warning"):
                    return False
        msg = (f"¿Confirma la programación?\n\nEquipo:\t\t{eq}\nPM:\t\tPM {fmt_tipo(sug)}\n"
               f"Horómetro objetivo:\t{fmt_num(proy)} h\nFecha programada:\t{fmt_fecha(fp)}")
        if f_act:
            msg += f"\n\nReemplaza la fecha anterior: {fmt_fecha(f_act)}"
        if not ui.si_no(msg):
            return False
        with self.repo.transaccion():
            self.escribir_programacion(eq, sug, proy, fp)
        self.recargar()
        ui.info(f"PM {fmt_tipo(sug)} del equipo {eq} programada para el {fmt_fecha(fp)}.")
        return True

    # ------------------------------------------------------ eliminar última PM
    def eliminar_ultima_pm(self, eq: str) -> bool:
        m, ui = self.m, self.ui
        if not self.equipo_valido(eq):
            return False
        filas = m.hist_eq.get(eq, [])
        if not filas:
            ui.aviso(f"El equipo {eq} no tiene PM registradas para eliminar.")
            return False
        lr = filas[-1]
        max_horo = max(float(f["horo"]) for f in filas if es_num(f["horo"]))
        if not es_num(lr["horo"]) or float(lr["horo"]) != max_horo:
            ui.error(f"La última fila del equipo {eq} no es la de mayor horómetro.\n"
                     "No se eliminó nada. Revise el Historial (orden de las filas) y vuelva a intentarlo.")
            return False
        n_ac = sum(1 for a in m.ac if a["id_pm"] == lr["id"] and a["equipo"].strip() == eq)
        msg = (f"Se eliminará la última PM registrada del equipo {eq}:\n\n"
               f"Tipo de PM:\tPM {fmt_tipo(lr['tipo'])}\nFecha:\t\t{fmt_fecha(lr['fecha'])}\n"
               f"Horómetro:\t{fmt_num(lr['horo'])} h\n"
               f"Programación:\t{fmt_fecha(lr['fprog']) if lr['fprog'] else 'No programada'}")
        if lr["obs"]:
            msg += f"\nObservación:\t{lr['obs']}"
        msg += (f"\nRegistros de aceite asociados: {n_ac}\n\n"
                "Todos los cálculos (incluidos los aceites) volverán al estado anterior.\n"
                "Esta acción no se puede deshacer. ¿Desea continuar?")
        if not ui.si_no(msg, defecto_no=True, icono="warning"):
            return False
        with self.repo.transaccion():
            for a in m.ac:
                if a["id_pm"] == lr["id"] and a["equipo"].strip() == eq:
                    self.repo.borrar_aceite(a["seq"])
            self.repo.borrar_historial(lr["seq"])
        self.recargar()
        fprog = lr["fprog"]
        e = m.estado(eq)
        with self.repo.transaccion():
            if fprog:
                self.escribir_programacion(eq, e["sugerido"], e["proyectado"], fprog)
            else:
                self.escribir_programacion(eq, 0, 0, None)
        self.recargar()
        e = m.estado(eq)
        ui.info(f"PM {fmt_tipo(lr['tipo'])} eliminada. La PM actual del equipo {eq} vuelve a ser la PM "
                f"{fmt_tipo(e['sugerido'])} a las {fmt_num(e['proyectado'])} h"
                + (f", programada para el {fmt_fecha(fprog)}." if fprog else ", sin programar."))
        return True

    # ------------------------------------------------- horas acumuladas aceites
    def recalcular_horas_aceites(self, silencioso: bool = False) -> int:
        filas = self.repo.aceites()
        claves, horos, valido = [], [], []
        for a in filas:
            claves.append(f"{a['equipo'].strip()}|{(a['comp'] or '').strip().lower()}")
            ok = a["origen"] != ORIGEN_NO and es_num(a["horo"]) and a["horo"] > 0
            valido.append(ok)
            horos.append(float(a["horo"]) if ok else 0.0)
        n = 0
        with self.repo.transaccion():
            for i, a in enumerate(filas):
                if valido[i]:
                    prev = max((horos[k] for k in range(len(filas))
                                if valido[k] and claves[k] == claves[i] and horos[k] < horos[i]), default=0.0)
                    nuevo = horos[i] - prev if prev > 0 else SIN_ANTERIOR
                    n += 1
                else:
                    nuevo = None
                if a["horas_ac"] != nuevo:
                    self.repo.actualizar_aceite(a["seq"], {"horas_ac": nuevo})
        self.recargar()
        if not silencioso:
            self.ui.info(f"Horas acumuladas recalculadas para {n} cambios de aceite.")
        return n

    # ------------------------------------------------- cambio de aceite individual
    def cambio_aceite_individual(self, eq: str) -> bool:
        m, ui = self.m, self.ui
        if not self.equipo_valido(eq):
            return False
        aceites = m.control_aceites(eq)
        if not aceites:
            ui.aviso(f"El equipo {eq} no tiene aceites configurados.")
            return False
        opciones = [a["componente"] + (f" ({fmt_num(a['acum'])} h)" if es_num(a["acum"]) else "") for a in aceites]
        sel = ui.elegir_varios(f"CAMBIO DE ACEITE INDIVIDUAL · {eq}\n\nMarque el o los aceites cambiados:", opciones)
        if not sel:
            return False
        nombres = [aceites[i]["componente"] for i in sel]
        ult = [m.ultimo_horo_aceite(eq, c) for c in nombres]
        max_ult = max(ult)
        horo_hoy = m.estado(eq)["horo_in"]
        while True:
            s = ui.pedir("Horómetro al que se cambió el aceite (h).\n\n"
                         + (f"Debe ser mayor o igual al último cambio registrado ({fmt_num(max_ult)} h)" if max_ult > 0
                            else "Sin cambio anterior registrado")
                         + (f" y menor o igual al horómetro de hoy ({fmt_num(horo_hoy)} h)." if horo_hoy is not None
                            else "."), "Cambio de aceite", fmt_tipo(horo_hoy) if horo_hoy is not None else "")
            if not s or not s.strip():
                return False
            horo = parse_num(s)
            msg = ""
            if horo is None:
                msg = "Ingrese un número."
            elif horo < max_ult:
                msg = f"El horómetro no puede ser menor al último cambio registrado ({fmt_num(max_ult)} h)."
            elif horo_hoy is not None and horo > horo_hoy:
                msg = f"El horómetro no puede superar el horómetro de hoy ({fmt_num(horo_hoy)} h)."
            if not msg:
                break
            ui.aviso(msg)
        while True:
            s = ui.pedir("Fecha del cambio de aceite (dd-mm-aaaa). No puede ser futura.", "Cambio de aceite",
                         fmt_fecha(m.hoy))
            if not s or not s.strip():
                return False
            d = parse_fecha(s)
            if d is None:
                ui.aviso(f"Fecha no válida: «{s}». Use el formato dd-mm-aaaa (por ejemplo 01-11-2026).")
            elif d > m.hoy:
                ui.aviso(f"La fecha no puede ser posterior a hoy ({fmt_fecha(m.hoy)}).")
            else:
                break
        res = "".join(f"\n- {c}" + (f" ({fmt_num(horo - u)} h acumuladas)" if u > 0 else " (sin cambio anterior)")
                      for c, u in zip(nombres, ult))
        if not ui.si_no(f"¿Confirma el CAMBIO DE ACEITE individual?\n\nEquipo: {eq}\nHorómetro: {fmt_num(horo)} h\n"
                        f"Fecha: {fmt_fecha(d)}\n{res}"):
            return False
        ahora = dt.datetime.now().replace(microsecond=0)
        reg = ahora if d == m.hoy else dt.datetime(d.year, d.month, d.day)
        with self.repo.transaccion():
            for c, u in zip(nombres, ult):
                self.repo.agregar_aceite({"id_pm": 0, "equipo": eq, "comp": c, "horo": horo, "origen": ORIGEN_IND,
                                          "reg_el": reg, "horas_ac": horo - u if u > 0 else SIN_ANTERIOR})
        self.recargar()
        ui.info(f"Cambio de aceite registrado ({len(nombres)} {'aceite' if len(nombres) == 1 else 'aceites'}) "
                f"para {eq} a las {fmt_num(horo)} h.\nLos contadores del Panel se reiniciaron.")
        return True

    # ---------------------------------------------------------- períodos
    def validar_desde(self, d1: dt.date) -> str:
        lim = sumar_meses(self.m.hoy, MESES_MAX)
        if d1 < dt.date(2023, 1, 1):
            return "La fecha DESDE no puede ser anterior al 01-01-2023."
        if d1 > lim:
            return f"La fecha DESDE no puede superar {MESES_MAX} meses desde hoy ({fmt_fecha(lim)})."
        return ""

    def validar_periodo(self, d1: dt.date, d2: dt.date) -> str:
        lim = sumar_meses(self.m.hoy, MESES_MAX)
        if d2 < d1:
            return f"La fecha HASTA debe ser igual o posterior a la fecha DESDE ({fmt_fecha(d1)})."
        if d2 > lim:
            return f"La fecha HASTA no puede superar {MESES_MAX} meses desde hoy ({fmt_fecha(lim)})."
        return ""

    def definir_periodo(self, s1: str, s2: str) -> bool:
        d1, d2 = parse_fecha(s1), parse_fecha(s2)
        if d1 is None:
            self.ui.aviso(f"Fecha DESDE no válida: «{s1}». Use el formato dd-mm-aaaa.")
            return False
        if d2 is None:
            self.ui.aviso(f"Fecha HASTA no válida: «{s2}». Use el formato dd-mm-aaaa.")
            return False
        msg = self.validar_desde(d1) or self.validar_periodo(d1, d2)
        if msg:
            self.ui.aviso(msg)
            return False
        per = self.repo.get_config("periodos", {})
        per.update(desde=d1.isoformat(), hasta=d2.isoformat())
        self.repo.set_config("periodos", per)
        r = self.m.periodo(d1, d2)
        self.ui.info(f"Período definido: {fmt_fecha(d1)} al {fmt_fecha(d2)}\n\n"
                     f"Total con margen: {fmt_num(r['total_con_margen'])} L  ·  {r['total_tarros']} tarros de "
                     f"{fmt_tipo(self.m.p['tarro'])} L.\n\nPresione «Exportar» para generar el Excel de compra.")
        return True

    def definir_semanas(self, s1: str, s_n: str) -> bool:
        d1 = parse_fecha(s1)
        lim = sumar_meses(self.m.hoy, MESES_MAX)
        if d1 is None:
            self.ui.aviso(f"Fecha de inicio no válida: «{s1}». Use el formato dd-mm-aaaa.")
            return False
        if d1 < dt.date(2023, 1, 1):
            self.ui.aviso("La fecha de inicio no puede ser anterior al 01-01-2023.")
            return False
        if d1 > lim:
            self.ui.aviso(f"La fecha de inicio no puede superar hoy + {MESES_MAX} meses ({fmt_fecha(lim)}).")
            return False
        n = parse_num(s_n)
        if n is None or n != int(n) or not 1 <= n <= SEM_MAX:
            self.ui.aviso(f"Ingrese un número entero de semanas entre 1 y {SEM_MAX}.")
            return False
        n = int(n)
        d2 = d1 + dt.timedelta(days=7 * n - 1)
        if d2 > lim:
            self.ui.aviso(f"El plazo terminaría el {fmt_fecha(d2)}, después de hoy + {MESES_MAX} meses "
                          f"({fmt_fecha(lim)}). Indique menos semanas.")
            return False
        per = self.repo.get_config("periodos", {})
        per.update(sem_ini=d1.isoformat(), sem_n=n)
        self.repo.set_config("periodos", per)
        s = self.m.semanas(d1, n)
        self.ui.info(f"Plazo: {fmt_fecha(d1)} al {fmt_fecha(d2)} ({n} {'semana' if n == 1 else 'semanas'}).\n\n"
                     f"PM del plazo: {s['n_pm_total']}\nTotal con margen: {fmt_num(s['total_con_margen'])} L  ·  "
                     f"{s['total_tarros']} tarros de {fmt_tipo(self.m.p['tarro'])} L.\n\n"
                     "Presione «Exportar» para generar el Excel con el detalle por semana y por PM.")
        return True


def _texto_horas(h) -> str:
    if h is None:
        return ""
    if es_num(h):
        return f" ({fmt_num(h)} h acumuladas)"
    return f" ({str(h).lower()})"


__all__ = ["Acciones", "UI", "mismo_texto"]
