"""Ventana principal: reemplaza las hojas y los botones del libro Excel."""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import openpyxl

from . import TITULO, __version__, exportar
from .acciones import Acciones
from .db import PARAMS_DEF, Repositorio
from .importar import extraer_hoja, importar_libro
from .motor import Motor
from .util import es_num, fmt_fecha, fmt_fechahora, fmt_num, fmt_pct, fmt_tipo, parse_num
from .widgets import (AZUL, NARANJA, ROJO, VERDE, Desplazable, DialogoFila, DialogoTexto, DialogoVarios,
                      EditorTabla, Tarjeta, llenar, tabla)

NOMBRE_DB = "PlanificacionPM_datos.db"


def carpeta_datos() -> Path:
    """Base de datos junto al ejecutable (fácil de respaldar); si no se puede escribir, en APPDATA."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    try:
        prueba = base / ".planpm_prueba"
        prueba.write_text("ok")
        prueba.unlink()
        return base
    except OSError:
        alt = Path(os.environ.get("APPDATA") or Path.home()) / "PlanificacionPM"
        alt.mkdir(parents=True, exist_ok=True)
        return alt


def abrir_archivo(ruta: str):
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta])
    except Exception as ex:  # pragma: no cover
        messagebox.showwarning(TITULO, f"No fue posible abrir el archivo:\n{ex}")


class UITk:
    """Implementación de la interfaz de diálogos (MsgBox / InputBox de VBA)."""

    def __init__(self, root):
        self.root = root

    def info(self, msg):
        messagebox.showinfo(TITULO, msg, parent=self.root)

    def aviso(self, msg):
        messagebox.showwarning(TITULO, msg, parent=self.root)

    def error(self, msg):
        messagebox.showerror(TITULO, msg, parent=self.root)

    def si_no(self, msg, defecto_no=False, icono="question"):
        return messagebox.askyesno(TITULO, msg, parent=self.root, icon=icono,
                                   default=messagebox.NO if defecto_no else messagebox.YES)

    def si_no_cancelar(self, msg):
        return messagebox.askyesnocancel(TITULO, msg, parent=self.root)

    def pedir(self, msg, titulo="", defecto=""):
        return DialogoTexto(self.root, msg, f"{TITULO} - {titulo}" if titulo else TITULO, defecto).resultado

    def elegir_varios(self, msg, opciones):
        return DialogoVarios(self.root, msg, opciones).resultado


class App(tk.Tk):
    def __init__(self, ruta_db: Path | None = None, hoy: dt.date | None = None):
        super().__init__()
        self.title(f"{TITULO} · Mantención preventiva de equipos de perforación (v{__version__})")
        self.geometry("1440x880")
        self.minsize(1000, 640)
        self._estilos()
        self.ruta_db = ruta_db or carpeta_datos() / NOMBRE_DB
        self.repo = Repositorio(self.ruta_db)
        self.ui = UITk(self)
        if self.repo.vacia() and not self._primer_inicio():
            self.after(10, self.destroy)
            return
        self.m = Motor(self.repo, hoy=hoy)
        self.acc = Acciones(self.m, self.ui)
        self.var_eq = tk.StringVar(value=self.repo.get_config("equipo_sel") or (self.m.lista_equipos() or [""])[0])
        self._construir()
        self.refrescar()
        self.after(300, self._al_abrir)

    # ------------------------------------------------------------------ estilo
    def _estilos(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        base = ("Segoe UI", 9)
        self.option_add("*Font", base)
        s.configure(".", font=base)
        self.configure(background="#FFFFFF")
        self.option_add("*Toplevel.background", "#FFFFFF")
        for est in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label", "TCheckbutton", "TNotebook"):
            s.configure(est, background="#FFFFFF")
        s.configure("Fondo.TFrame", background="#FFFFFF")
        s.configure("Tarjeta.TFrame", background="#F2F2F2", relief="flat")
        s.configure("TarjetaTit.TLabel", background="#F2F2F2", foreground="#595959", font=("Segoe UI", 8))
        s.configure("TarjetaVal.TLabel", background="#F2F2F2", foreground=AZUL, font=("Segoe UI", 11, "bold"))
        s.configure("Seccion.TLabelframe", background="#FFFFFF")
        s.configure("Seccion.TLabelframe.Label", foreground=AZUL, background="#FFFFFF", font=("Segoe UI", 10, "bold"))
        s.configure("Titulo.TLabel", foreground=AZUL, font=("Segoe UI", 14, "bold"))
        s.configure("Nota.TLabel", foreground="#595959")
        s.configure("Alerta.TLabel", foreground=ROJO, font=("Segoe UI", 10, "bold"))
        s.configure("Accion.TButton", font=("Segoe UI", 9, "bold"))
        s.configure("Treeview", rowheight=22)
        s.configure("Treeview.Heading", background=AZUL, foreground="#FFFFFF", font=("Segoe UI", 9, "bold"))
        s.map("Treeview.Heading", background=[("active", "#2E75B6")])
        for nombre, color in (("Verde", VERDE), ("Rojo", ROJO), ("Azul", "#2E75B6"), ("Naranja", NARANJA),
                              ("Gris", "#767676"), ("Morado", "#7030A0")):
            s.configure(f"{nombre}.TButton", background=color, foreground="#FFFFFF", font=("Segoe UI", 9, "bold"),
                        padding=(10, 5))
            s.map(f"{nombre}.TButton", background=[("active", color), ("pressed", AZUL)])

    def _boton(self, parent, texto, cmd, color="Azul", **kw):
        return ttk.Button(parent, text=texto, command=cmd, style=f"{color}.TButton", **kw)

    def _seccion(self, parent, titulo):
        return ttk.LabelFrame(parent, text=titulo, style="Seccion.TLabelframe", padding=8)

    # ------------------------------------------------------------ primer inicio
    def _primer_inicio(self) -> bool:
        messagebox.showinfo(
            TITULO, "Bienvenido.\n\nLa base de datos está vacía. Seleccione el libro Excel original "
                    "(Planificacion_PM .xlsm) para importar el Historial, los cambios de aceite, las lecturas, "
                    "la programación, la configuración, los kits y los formatos de solicitud de análisis.\n\n"
                    f"Los datos se guardarán en:\n{self.ruta_db}")
        ruta = filedialog.askopenfilename(title="Libro Excel a importar",
                                          filetypes=[("Libro de Excel", "*.xlsm *.xlsx"), ("Todos", "*.*")])
        if not ruta:
            messagebox.showwarning(TITULO, "No se importó ningún libro. El programa se cerrará.")
            return False
        try:
            r = importar_libro(ruta, self.repo)
        except Exception as ex:
            messagebox.showerror(TITULO, f"No fue posible importar el libro.\nDetalle: {ex}")
            self.repo.vaciar_todo()
            self.repo.cx.commit()
            return False
        messagebox.showinfo(TITULO, f"Importación terminada:\n- {r.get('historial', 0)} PM del Historial\n"
                                    f"- {r.get('aceites', 0)} registros de aceite\n"
                                    f"- {r.get('plantillas', 0)} formatos de solicitud de análisis")
        return True

    def _al_abrir(self):
        """Auto_Open: solicita el horómetro de hoy del equipo seleccionado."""
        self.acc.actualizar_horometro(self.var_eq.get(), al_abrir=True)
        self.refrescar()

    # ---------------------------------------------------------------- armado
    def _construir(self):
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text="PLANIFICACIÓN DE MANTENCIÓN PREVENTIVA · EQUIPOS DE PERFORACIÓN",
                  style="Titulo.TLabel").grid(row=0, column=0, columnspan=10, sticky="w")
        ttk.Label(top, text="EQUIPO").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.cb_eq = ttk.Combobox(top, textvariable=self.var_eq, values=self.m.lista_equipos(), width=8,
                                  state="readonly", font=("Segoe UI", 12, "bold"))
        self.cb_eq.grid(row=1, column=1, padx=(4, 16), pady=(6, 0))
        self.cb_eq.bind("<<ComboboxSelected>>", lambda _e: self._cambio_equipo())
        self.lbl_modelo = ttk.Label(top, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_modelo.grid(row=1, column=2, padx=(0, 16), pady=(6, 0))
        self.lbl_horo = ttk.Label(top, text="", font=("Segoe UI", 10))
        self.lbl_horo.grid(row=1, column=3, padx=(0, 10), pady=(6, 0))
        self._boton(top, "Actualizar horómetro", self._actualizar_horo).grid(row=1, column=4, pady=(6, 0))
        self.lbl_alerta = ttk.Label(top, text="", style="Alerta.TLabel")
        self.lbl_alerta.grid(row=1, column=5, padx=12, pady=(6, 0), sticky="w")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tabs = {}
        for nombre, fn in (("Panel", self._tab_panel), ("Historial", self._tab_historial),
                           ("Aceites", self._tab_aceites), ("Proyección", self._tab_proyeccion),
                           ("Proyección aceites", self._tab_proy_aceites),
                           ("Aceites por semanas", self._tab_semanas), ("Kits a solicitar", self._tab_kits_sol),
                           ("Kits PM", self._tab_kits_pm), ("Lecturas y programación", self._tab_lecturas),
                           ("Configuración", self._tab_config), ("Instrucciones", self._tab_instrucciones)):
            f = ttk.Frame(self.nb, padding=6)
            self.nb.add(f, text=nombre)
            self.tabs[nombre] = f
            fn(f)

    # ---------------------------------------------------------------- PANEL
    def _tab_panel(self, tab):
        d = Desplazable(tab)
        d.pack(fill="both", expand=True)
        p = d.interior
        # PM ACTUAL
        s1 = self._seccion(p, "PM ACTUAL")
        s1.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.t = {}
        for i, (k, tit) in enumerate((("pm", "PM actual (pendiente)"), ("est_prog", "Estado de programación"),
                                      ("obj", "Horómetro objetivo"), ("venc", "Vencimiento proyectado"),
                                      ("fprog", "Fecha programada"), ("cumpl", "Cumplimiento última PM"),
                                      ("fsug", "Fecha sugerida para programar"))):
            t = Tarjeta(s1, tit)
            t.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
            self.t[k] = t
        self.lbl_detalle = ttk.Label(s1, text="", wraplength=430, style="Nota.TLabel")
        self.lbl_detalle.grid(row=3, column=0, columnspan=3, sticky="w", pady=(2, 6))
        fp = ttk.Frame(s1)
        fp.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(fp, text="Asignar fecha programada (dd-mm-aaaa):").pack(side="left")
        self.var_fprog = tk.StringVar()
        ttk.Entry(fp, textvariable=self.var_fprog, width=12).pack(side="left", padx=6)
        self._boton(fp, "Programar PM", self._programar).pack(side="left")
        self.lbl_nota_prog = ttk.Label(s1, text="", style="Nota.TLabel", wraplength=430)
        self.lbl_nota_prog.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # ESTADO DE MANTENCIÓN
        s2 = self._seccion(p, "ESTADO DE MANTENCIÓN")
        s2.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        for i, (k, tit) in enumerate((("ult", "Última PM ejecutada"), ("ult_horo", "Horómetro última PM"),
                                      ("ult_fecha", "Fecha última PM"), ("prom", "Promedio real (h/día)"),
                                      ("acum", "Horas acumuladas"), ("rest", "Horas para la PM actual"),
                                      ("estado", "Estado de la PM actual"), ("post", "Próxima PM (posterior)"),
                                      ("post_horo", "Horómetro próxima PM"), ("post_fecha", "Fecha estimada"),
                                      ("semana", "Semana actual"))):
            t = Tarjeta(s2, tit, 16)
            t.grid(row=i // 4, column=i % 4, sticky="nsew", padx=3, pady=3)
            self.t[k] = t

        # CONTROL DE ACEITES
        s3 = self._seccion(p, "CONTROL DE ACEITES")
        s3.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        self.s3 = s3
        m, self.tv_ac = tabla(s3, [("c", "Componente", 190, "w"), ("f", "Frec. (h)", 60, "center"),
                                   ("u", "Últ. cambio", 80, "center"), ("a", "Acumuladas", 80, "center"),
                                   ("r", "Restantes", 70, "center"), ("e", "Estado", 110, "center"),
                                   ("t", "Frecuencia de cambio", 150, "w")], height=13)
        m.pack(fill="both", expand=True)
        b = ttk.Frame(s3)
        b.pack(fill="x", pady=(6, 0))
        self._boton(b, "Cambio de aceite", self._cambio_aceite, "Naranja").pack(side="left")
        self._boton(b, "Solicitud de análisis", self._solicitud, "Verde").pack(side="left", padx=6)

        # AVANCE DE HORÓMETRO PROYECTADO
        s4 = self._seccion(p, "AVANCE DE HORÓMETRO PROYECTADO")
        s4.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.s4 = s4
        m, self.tv_av = tabla(s4, [("a", "Avance", 190, "w"), ("d", "Diario (h/día)", 90, "center"),
                                   ("s", "Semanal (h)", 90, "center"), ("m", "Mensual (h)", 90, "center"),
                                   ("h", "Horómetro estimado hoy", 150, "center"), ("p", "Horómetro a fecha", 190, "center"),
                                   ("o", "Objetivo PM (h)", 120, "center"), ("dif", "Diferencia vs objetivo (h)", 160, "center")],
                              height=2, stretch_last=False)
        m.pack(fill="x")

        # DATOS DE LA PM A DAR POR EJECUTADA
        s5 = self._seccion(p, "DATOS DE LA PM A DAR POR EJECUTADA")
        s5.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.var_tipo = tk.StringVar()
        self.var_fecha = tk.StringVar()
        self.var_horo = tk.StringVar()
        self.var_obs = tk.StringVar()
        ttk.Label(s5, text="Tipo de PM").grid(row=0, column=0, sticky="w")
        self.cb_tipo = ttk.Combobox(s5, textvariable=self.var_tipo, width=10, state="readonly")
        self.cb_tipo.grid(row=0, column=1, sticky="w", pady=2)
        self.lbl_tipo_sug = ttk.Label(s5, text="", style="Nota.TLabel")
        self.lbl_tipo_sug.grid(row=0, column=2, sticky="w", padx=8)
        ttk.Label(s5, text="Fecha de ejecución").grid(row=1, column=0, sticky="w")
        ttk.Entry(s5, textvariable=self.var_fecha, width=12).grid(row=1, column=1, sticky="w", pady=2)
        self.lbl_horas_desde = ttk.Label(s5, text="", style="Nota.TLabel")
        self.lbl_horas_desde.grid(row=1, column=2, sticky="w", padx=8)
        ttk.Label(s5, text="Horómetro de ejecución (h)").grid(row=2, column=0, sticky="w")
        e = ttk.Entry(s5, textvariable=self.var_horo, width=12)
        e.grid(row=2, column=1, sticky="w", pady=2)
        self.var_horo.trace_add("write", lambda *_: self._horas_desde())
        self.lbl_prog_form = ttk.Label(s5, text="", style="Nota.TLabel")
        self.lbl_prog_form.grid(row=2, column=2, sticky="w", padx=8)
        ttk.Label(s5, text="Observación (opcional)").grid(row=3, column=0, sticky="w")
        ttk.Entry(s5, textvariable=self.var_obs, width=48).grid(row=3, column=1, columnspan=2, sticky="w", pady=2)
        b = ttk.Frame(s5)
        b.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._boton(b, "Dar ejecutada", self._dar_ejecutada, "Verde").pack(side="left")
        self._boton(b, "Limpiar formulario", self._restaurar_form, "Gris").pack(side="left", padx=6)
        self._boton(b, "Eliminar última PM", self._eliminar, "Rojo").pack(side="left")
        ttk.Label(s5, text="Valores propuestos automáticamente: modifíquelos solo si la PM real difiere. «Dar "
                           "ejecutada» registra la PM y confirma aceite por aceite. «Eliminar última PM» deshace el "
                           "último registro del equipo.", style="Nota.TLabel", wraplength=480
                  ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # ÚLTIMAS PM
        s6 = self._seccion(p, "ÚLTIMAS PM REGISTRADAS DEL EQUIPO")
        s6.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        m, self.tv_ult = tabla(s6, [("t", "Tipo PM", 70, "center"), ("f", "Fecha ejecución", 100, "center"),
                                    ("h", "Horómetro", 80, "center"), ("i", "Horas intervalo", 95, "center"),
                                    ("p", "Programada", 90, "center")], height=6)
        m.pack(fill="both", expand=True)

        # KIT + PROYECCIÓN 6 MESES
        s7 = self._seccion(p, "KIT DE MANTENIMIENTO")
        s7.grid(row=3, column=1, rowspan=2, sticky="nsew", padx=4, pady=4)
        self.s7 = s7
        self.lbl_kit = ttk.Label(s7, text="", font=("Segoe UI", 9, "bold"), foreground=AZUL, wraplength=640,
                                 justify="left")
        self.lbl_kit.pack(anchor="w")
        m, self.tv_kit = tabla(s7, [("n", "N° de parte", 130, "w"), ("c", "Cantidad", 70, "center"),
                                    ("u", "Ubicación", 90, "center"), ("k", "Comentario", 300, "w")], height=14)
        m.pack(fill="both", expand=True)

        s8 = self._seccion(p, "PROYECCIÓN 6 MESES (resumen · detalle en la pestaña Proyección)")
        s8.grid(row=4, column=0, sticky="nsew", padx=4, pady=4)
        self.s8 = s8
        m, self.tv_6m = tabla(s8, [("m", "Mes", 120, "w"), ("a", "PM 250", 70, "center"), ("b", "PM 500", 70, "center"),
                                   ("c", "PM 1000", 70, "center"), ("d", "PM cierre", 80, "center"),
                                   ("t", "Total", 60, "center")], height=7, stretch_last=False)
        m.pack(fill="x")
        for c in range(2):
            p.columnconfigure(c, weight=1, uniform="panel")

    def _restaurar_form(self):
        e = self.m.estado(self.eq)
        self.cb_tipo.configure(values=[str(t) for t in self.m.tipos_validos(e["modelo"])])
        self.var_tipo.set(fmt_tipo(e["sugerido"]))
        self.var_fecha.set(fmt_fecha(self.m.hoy))
        self.var_horo.set(fmt_tipo(e["horo_in"]) if e["horo_in"] is not None else "")
        self.var_obs.set("")
        self._horas_desde()

    def _horas_desde(self):
        try:
            e = self.m.estado(self.eq)
        except Exception:
            return
        h = parse_num(self.var_horo.get())
        txt = f"Horas desde últ. PM: {fmt_num(h - e['ult_horo'])}" if (e["n"] > 0 and h is not None) else \
            "Horas desde últ. PM: -"
        self.lbl_horas_desde.configure(text=txt)

    def _refrescar_panel(self):
        m, eq = self.m, self.eq
        e = m.estado(eq)
        hay = e["n"] > 0
        lect = e["con_lectura"]
        self.lbl_modelo.configure(text=f"MODELO / FAENA: {e['modelo']} / {e['faena']}")
        self.lbl_horo.configure(text=f"HORÓMETRO DE HOY: {fmt_num(e['horo_in']) if lect else '-'} h   ·   "
                                     f"FECHA LECTURA: {fmt_fecha(e['fecha_lect']) or '-'}")
        self.lbl_alerta.configure(text=e["alerta"])
        col_prog = {"PROGRAMADA": VERDE, "PROGRAMADA CON RIESGO": NARANJA, "PROGRAMACIÓN VENCIDA": ROJO,
                    "NO PROGRAMADA": ROJO}.get(e["estado_prog"], AZUL)
        self.t["pm"].set(f"PM {fmt_tipo(e['sugerido'])}" if hay else "-")
        self.t["est_prog"].set(e["estado_prog"], col_prog)
        self.t["obj"].set(e["proyectado"] if hay else "-")
        self.t["venc"].set(e["fecha_proy"] if hay and lect else "-")
        self.t["fprog"].set(e["fprog"] or "Sin programar")
        self.t["cumpl"].set(e["cumplimiento"])
        self.t["fsug"].set(e["fecha_sug"] if hay and lect else "-",
                           titulo="Fecha sugerida para programar" if not hay else
                           f"Fecha sugerida ({e['margen_dias']} {'día' if e['margen_dias'] == 1 else 'días'} antes)")
        self.lbl_detalle.configure(text=e["detalle_prog"])
        self.lbl_nota_prog.configure(text="Fecha vacía + «Programar PM» = anular la programación vigente.  ·  "
                                          f"Margen de seguridad: {fmt_pct(m.p['margen_prog'])} de los días restantes.")
        col_est = {"Vencida": ROJO, "Próxima": NARANJA, "En plazo": VERDE}.get(e["estado"], AZUL)
        self.t["ult"].set(f"PM {fmt_tipo(e['ult_tipo'])}" if hay else "Sin registros")
        self.t["ult_horo"].set(e["ult_horo"] if hay else "-")
        self.t["ult_fecha"].set(e["ult_fecha"] if hay else "-")
        self.t["prom"].set(fmt_num(e["promedio"], 1),
                           titulo=f"Promedio real últimas {fmt_tipo(m.p['pm_prom'])} PM (h/día)" if e["base"]
                           else "Promedio por defecto (h/día)")
        self.t["acum"].set(e["acum"] if hay else "-")
        self.t["rest"].set(e["rest"] if hay else "-", ROJO if hay and e["rest"] <= 0 else None)
        self.t["estado"].set(e["estado"], col_est)
        self.t["post"].set(f"PM {fmt_tipo(e['posterior'])}" if hay else "-")
        self.t["post_horo"].set(e["horo_post"] if hay else "-")
        self.t["post_fecha"].set(e["fecha_post"] if hay and lect else "-")
        self.t["semana"].set(f"S{m.hoy.isocalendar()[1]:02d}")
        # Aceites
        self.s3.configure(text=f"CONTROL DE ACEITES · MODELO {e['modelo']} (horas desde el último cambio)")
        filas, tags = [], []
        for a in m.control_aceites(eq):
            filas.append([a["componente"], a["frecuencia"], a["ult"], a["acum"], a["rest"], a["estado"], a["texto"]])
            tags.append({"Cambio vencido": "rojo", "Cambio próximo": "amarillo", "En condiciones": "verde"}
                        .get(a["estado"], ""))
        llenar(self.tv_ac, filas, tags)
        # Avance
        self.s4.configure(text=f"AVANCE DE HORÓMETRO PROYECTADO · EQUIPO {eq}   (cálculos con avance real + "
                               f"{fmt_pct(m.p['avance_extra'])})")
        ok = hay and lect
        ref = "(programada)" if (e["fprog"] and e["fprog"] >= m.hoy) else "(sugerida)"
        self.tv_av.heading("p", text=f"Horómetro al {e['fecha_av_pm']:%d-%m} {ref}")
        self.tv_av.heading("o", text=f"Objetivo PM {fmt_tipo(e['sugerido'])} (h)")
        llenar(self.tv_av, [
            ["Real (promedio últimas PM)", fmt_num(e["promedio"], 2), fmt_num(e["av_sem"], 1), fmt_num(e["av_mes"], 1),
             e["horo_est_hoy_real"] if ok else "-", e["horo_av_pm_real"] if ok else "-",
             e["proyectado"] if hay else "-", e["horo_av_pm_real"] - e["proyectado"] if ok else "-"],
            [f"Con +{fmt_pct(m.p['avance_extra'])} (usado en cálculos)", fmt_num(e["promedio_proy"], 2),
             fmt_num(e["promedio_proy"] * 7, 1), fmt_num(e["promedio_proy"] * 30, 1),
             e["horo_est_hoy"] if ok else "-", e["horo_av_pm"] if ok else "-", "",
             e["horo_av_pm"] - e["proyectado"] if ok else "-"]],
            ["rojo" if ok and e["horo_av_pm_real"] > e["proyectado"] else "",
             "rojo" if ok and e["horo_av_pm"] > e["proyectado"] else ""])
        # Formulario
        self._restaurar_form()
        self.lbl_tipo_sug.configure(text=f"Tipo sugerido: PM {fmt_tipo(e['sugerido'])}")
        self.lbl_prog_form.configure(text=f"Programación: {fmt_fecha(e['fprog']) if e['fprog'] else 'No programada'}")
        # Últimas PM
        filas = []
        for f in list(reversed(m.hist_eq.get(eq, [])))[:6]:
            filas.append([f"PM {fmt_tipo(f['tipo'])}", f["fecha"], f["horo"], f["horas"], f["fprog"] or "No"])
        llenar(self.tv_ult, filas)
        # Kit
        kits = m.kits_de(e["modelo"], e["sugerido"])
        self.s7.configure(text=f"KIT DE MANTENIMIENTO · PM {fmt_tipo(e['sugerido'])} · {e['modelo']}"
                               + (f"  ({len(kits)} kits)" if len(kits) > 1 else ""))
        filas, tags, txt = [], [], []
        for k in kits:
            txt.append(f"Kit {k['kit']}  ·  Ubicación {k['ubic_kit']}  ·  Equipos {k['equipos_txt']}")
            if len(kits) > 1:
                filas.append([f"KIT {k['kit']}", "", k["ubic_kit"], f"Equipos {k['equipos_limpio']}"])
                tags.append("total")
            for ln in k["lineas"]:
                sub = ln["tipo_linea"] == "SUB"
                filas.append([ln["np"], "" if sub else ln["cant"], "" if sub else ln["ubic"], ln["com"]])
                tags.append("kit" if sub else "")
        self.lbl_kit.configure(text="\n".join(txt) if txt else "Sin kit definido")
        llenar(self.tv_kit, filas, tags)
        # 6 meses
        r6 = m.resumen_meses(eq, 6)
        self.tv_6m.heading("d", text=f"PM {r6['tipos'][-1]}")
        filas = [[f["mes"].strftime("%m-%Y"), *f["cuenta"], f["total"]] for f in r6["filas"]]
        filas.append(["Total período", *r6["total"], sum(r6["total"])])
        llenar(self.tv_6m, filas, [""] * 6 + ["total"])

    # --------------------------------------------------------- acciones Panel
    @property
    def eq(self):
        return self.var_eq.get()

    def _cambio_equipo(self):
        self.repo.set_config("equipo_sel", self.eq)
        self.refrescar()

    def _actualizar_horo(self):
        if self.acc.actualizar_horometro(self.eq):
            self.refrescar()

    def _dar_ejecutada(self):
        if self.acc.dar_ejecutada(self.eq, self.var_tipo.get(), self.var_fecha.get(), self.var_horo.get(),
                                  self.var_obs.get()):
            self.refrescar()
        else:
            self.refrescar(solo_calculo=True)

    def _programar(self):
        if self.acc.programar_pm(self.eq, self.var_fprog.get()):
            self.var_fprog.set("")
            self.refrescar()

    def _eliminar(self):
        if self.acc.eliminar_ultima_pm(self.eq):
            self.refrescar()

    def _cambio_aceite(self):
        if self.acc.cambio_aceite_individual(self.eq):
            self.refrescar()

    def _guardar_como(self, nombre, titulo):
        ruta = filedialog.asksaveasfilename(parent=self, title=titulo, initialfile=nombre,
                                            initialdir=str(self.ruta_db.parent), defaultextension=".xlsx",
                                            filetypes=[("Libro de Excel", "*.xlsx")])
        if not ruta:
            return None
        if not ruta.lower().endswith(".xlsx"):
            ruta += ".xlsx"
        return ruta

    def _tras_exportar(self, msg, ruta):
        if messagebox.askyesno(TITULO, f"{msg}\n\n¿Desea abrir el archivo exportado?", parent=self):
            abrir_archivo(ruta)

    def _error_export(self, ex):
        messagebox.showerror(TITULO, f"No fue posible exportar.\nDetalle: {ex}\n\n"
                                     "Si el archivo de destino está abierto, ciérrelo y vuelva a intentarlo.", parent=self)

    def _solicitud(self):
        eq = self.eq
        if not self.acc.equipo_valido(eq):
            return
        filas = self.m.hist_eq.get(eq, [])
        if not filas:
            self.ui.aviso(f"El equipo {eq} no tiene PM ejecutadas en el Historial.")
            return
        ult = max(filas, key=lambda f: f["id"])
        ruta = self._guardar_como(f"Solicitud_analisis_lubricante_{eq}_PM{fmt_tipo(ult['tipo'])}_"
                                  f"{self.m.hoy:%d-%m-%Y}.xlsx", "Exportar solicitud de análisis de lubricante")
        if not ruta:
            return
        try:
            r = exportar.exportar_solicitud(self.m, eq, ruta)
        except Exception as ex:
            self._error_export(ex)
            return
        self._tras_exportar(f"Solicitud de análisis exportada:\n{ruta}\n\nEquipo {eq} · PM {fmt_tipo(r['tipo'])} del "
                            f"{fmt_fecha(r['fecha'])} ({fmt_num(r['horo'])} h)\n"
                            f"Aceites cambiados (SI): {r['n_si']} de {r['n_filas']}.", ruta)

    # -------------------------------------------------------------- HISTORIAL
    COLS_HIST = [("id", "ID", 50, "center"), ("equipo", "Equipo", 60, "center"), ("modelo", "Modelo", 70, "center"),
                 ("faena", "Faena", 55, "center"), ("tipo", "Tipo PM", 65, "center"),
                 ("fecha", "Fecha ejecución", 100, "center"), ("horo", "Horómetro", 80, "center"),
                 ("horas", "Horas desde PM anterior", 140, "center"), ("fprog", "Fecha programada", 105, "center"),
                 ("obs", "Observación", 260, "w"), ("reg_el", "Registrado el", 120, "center"),
                 ("reg_por", "Registrado por", 160, "w"), ("pos", "Pos. ciclo", 70, "center")]

    def _barra_filtro(self, parent, var, al_cambiar):
        f = ttk.Frame(parent)
        ttk.Label(f, text="Equipo:").pack(side="left")
        cb = ttk.Combobox(f, textvariable=var, width=8, state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: al_cambiar())
        return f, cb

    def _tab_historial(self, tab):
        ttk.Label(tab, text="HISTORIAL DE MANTENCIONES PREVENTIVAS EJECUTADAS", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Registros generados con «Dar ejecutada» y eliminables con «Eliminar última PM» del Panel. "
                            "Doble clic para editar una fila (las posiciones de ciclo se recalculan solas).",
                  style="Nota.TLabel").pack(anchor="w")
        barra = ttk.Frame(tab)
        barra.pack(fill="x", pady=6)
        self.var_fh = tk.StringVar(value="Todos")
        f, self.cb_fh = self._barra_filtro(barra, self.var_fh, self._refrescar_historial)
        f.pack(side="left")
        self._boton(barra, "Editar fila", self._editar_hist).pack(side="left", padx=6)
        self._boton(barra, "Reparar claves", lambda: (self.acc.reparar_claves(), self.refrescar()), "Gris"
                    ).pack(side="left")
        self._boton(barra, "Corregir fechas futuras", lambda: (self.acc.corregir_fechas_futuras(), self.refrescar()),
                    "Gris").pack(side="left", padx=6)
        self._boton(barra, "Exportar tabla a Excel", self._exportar_hist, "Verde").pack(side="left")
        self.lbl_nh = ttk.Label(barra, text="", style="Nota.TLabel")
        self.lbl_nh.pack(side="right")
        m, self.tv_h = tabla(tab, self.COLS_HIST, height=25)
        m.pack(fill="both", expand=True)
        self.tv_h.bind("<Double-1>", lambda _e: self._editar_hist())

    def _filas_hist(self):
        fil = self.var_fh.get()
        return [f for f in self.m.hist if fil in ("", "Todos") or f["equipo"] == fil]

    def _refrescar_historial(self):
        filas = self._filas_hist()
        self._hist_vista = filas
        datos = []
        for f in filas:
            datos.append([str(f["id"]), f["equipo"], f["modelo"], f["faena"], fmt_tipo(f["tipo"]), f["fecha"], f["horo"],
                          f["horas"], f["fprog"], f["obs"], fmt_fechahora(f["reg_el"]), f["reg_por"],
                          f["pos"] if f["pos"] is not None else ""])
        llenar(self.tv_h, datos)
        if self.tv_h.get_children():
            self.tv_h.see(self.tv_h.get_children()[-1])
        self.lbl_nh.configure(text=f"{len(filas)} registro(s)")

    def _editar_hist(self):
        s = self.tv_h.selection()
        if not s:
            self.ui.aviso("Seleccione una fila del Historial.")
            return
        f = self._hist_vista[self.tv_h.index(s[0])]
        cols = [("tipo", "Tipo PM", "num", 80), ("fecha", "Fecha ejecución (dd-mm-aaaa)", "fecha", 100),
                ("horo", "Horómetro", "num", 80), ("horas", "Horas desde PM anterior", "num", 80),
                ("fprog", "Fecha programada (dd-mm-aaaa)", "fecha", 100), ("obs", "Observación", "txt", 400)]
        d = DialogoFila(self, f"Editar PM ID {f['id']} · {f['equipo']}", cols, f)
        if d.resultado is None:
            return
        with self.repo.transaccion():
            self.repo.actualizar_historial(f["seq"], d.resultado)
        self.m.recargar()
        self.acc.reparar_claves(silencioso=True)
        self.refrescar()

    def _exportar_tabla(self, nombre, titulo, cols, filas):
        ruta = self._guardar_como(nombre, titulo)
        if not ruta:
            return
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = titulo[:31]
            for j, c in enumerate(cols):
                ws.cell(1, 1 + j, c[1])
            for i, f in enumerate(filas):
                for j, v in enumerate(f):
                    cel = ws.cell(2 + i, 1 + j, v)
                    if isinstance(v, dt.datetime):
                        cel.number_format = "dd-mm-yyyy hh:mm"
                    elif isinstance(v, dt.date):
                        cel.number_format = "dd-mm-yyyy"
            exportar.formato_tabla(ws, 1, 1, len(filas) + 1, len(cols), 0)
            for j, c in enumerate(cols):
                ws.column_dimensions[openpyxl.utils.get_column_letter(1 + j)].width = max(10, c[2] // 7)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            wb.save(ruta)
        except Exception as ex:
            self._error_export(ex)
            return
        self._tras_exportar(f"Tabla exportada:\n{ruta}", ruta)

    def _exportar_hist(self):
        self._exportar_tabla("Historial_PM.xlsx", "Historial", self.COLS_HIST,
                             [[f[c[0]] for c in self.COLS_HIST] for f in self._filas_hist()])

    # ---------------------------------------------------------------- ACEITES
    COLS_AC = [("id_pm", "ID PM", 55, "center"), ("equipo", "Equipo", 60, "center"),
               ("comp", "Componente", 220, "w"), ("horo", "Horómetro cambio", 110, "center"),
               ("origen", "Origen", 120, "center"), ("reg_el", "Registrado el", 120, "center"),
               ("horas_ac", "Horas acumuladas al cambio", 170, "center")]

    def _tab_aceites(self, tab):
        ttk.Label(tab, text="REGISTRO DE CAMBIOS DE ACEITE", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Se registra con «Dar ejecutada» o «Cambio de aceite» y se borra con «Eliminar última PM». "
                            "«No cambiado» = correspondía pero aún no se ha cambiado.", style="Nota.TLabel").pack(anchor="w")
        barra = ttk.Frame(tab)
        barra.pack(fill="x", pady=6)
        self.var_fa = tk.StringVar(value="Todos")
        f, self.cb_fa = self._barra_filtro(barra, self.var_fa, self._refrescar_aceites)
        f.pack(side="left")
        self._boton(barra, "Editar fila", self._editar_ac).pack(side="left", padx=6)
        self._boton(barra, "Recalcular horas acumuladas",
                    lambda: (self.acc.recalcular_horas_aceites(), self.refrescar()), "Gris").pack(side="left")
        self._boton(barra, "Exportar tabla a Excel", self._exportar_ac, "Verde").pack(side="left", padx=6)
        self.lbl_na = ttk.Label(barra, text="", style="Nota.TLabel")
        self.lbl_na.pack(side="right")
        m, self.tv_a = tabla(tab, self.COLS_AC, height=25)
        m.pack(fill="both", expand=True)
        self.tv_a.bind("<Double-1>", lambda _e: self._editar_ac())

    def _filas_ac(self):
        fil = self.var_fa.get()
        return [a for a in self.m.ac if fil in ("", "Todos") or a["equipo"] == fil]

    def _refrescar_aceites(self):
        filas = self._filas_ac()
        self._ac_vista = filas
        llenar(self.tv_a, [[str(a["id_pm"]), a["equipo"], a["comp"], a["horo"], a["origen"], fmt_fechahora(a["reg_el"]),
                            a["horas_ac"]] for a in filas])
        if self.tv_a.get_children():
            self.tv_a.see(self.tv_a.get_children()[-1])
        self.lbl_na.configure(text=f"{len(filas)} registro(s)")

    def _editar_ac(self):
        s = self.tv_a.selection()
        if not s:
            self.ui.aviso("Seleccione una fila de la tabla de aceites.")
            return
        a = self._ac_vista[self.tv_a.index(s[0])]
        d = DialogoFila(self, f"Editar cambio de aceite · {a['equipo']}",
                        [("comp", "Componente", "txt", 300), ("horo", "Horómetro cambio", "num", 80),
                         ("origen", "Origen (En PM / Fuera de PM / No cambiado / Cambio individual)", "txt", 200)], a)
        if d.resultado is None:
            return
        with self.repo.transaccion():
            self.repo.actualizar_aceite(a["seq"], d.resultado)
        self.m.recargar()
        if messagebox.askyesno(TITULO, "¿Recalcular las horas acumuladas de todos los cambios de aceite?", parent=self):
            self.acc.recalcular_horas_aceites(silencioso=True)
        self.refrescar()

    def _exportar_ac(self):
        self._exportar_tabla("Cambios_aceite.xlsx", "Aceites", self.COLS_AC,
                             [[a[c[0]] for c in self.COLS_AC] for a in self._filas_ac()])

    # ------------------------------------------------------------- PROYECCIÓN
    def _tab_proyeccion(self, tab):
        self.lbl_proy_tit = ttk.Label(tab, text="", style="Titulo.TLabel")
        self.lbl_proy_tit.pack(anchor="w")
        ttk.Label(tab, text="Parte de la PM actual (fecha programada o proyectada) y suma el intervalo por PM al ritmo "
                            "del avance proyectado, siguiendo el ciclo del modelo.", style="Nota.TLabel").pack(anchor="w")
        m, self.tv_pm = tabla(tab, [("m", "Mes", 90, "w"), ("a", "PM 250", 70, "center"), ("b", "PM 500", 70, "center"),
                                    ("c", "PM 1000", 70, "center"), ("d", "PM cierre", 80, "center"),
                                    ("t", "Total", 60, "center"), ("x", "Detalle (fecha estimada)", 600, "w")], height=8)
        m.pack(fill="x", pady=6)
        ttk.Label(tab, text="PM proyectadas", style="Seccion.TLabelframe.Label").pack(anchor="w")
        m, self.tv_pl = tabla(tab, [("k", "N°", 50, "center"), ("t", "Tipo PM", 80, "center"),
                                    ("h", "Horómetro objetivo", 130, "center"), ("f", "Fecha estimada", 120, "center"),
                                    ("s", "Semana", 80, "center"), ("x", "", 100, "w")], height=20)
        m.pack(fill="both", expand=True)

    def _refrescar_proyeccion(self):
        eq = self.eq
        self.lbl_proy_tit.configure(text=f"PROYECCIÓN DE PM A 6 MESES · EQUIPO {eq}")
        r = self.m.resumen_meses(eq, 6)
        self.tv_pm.heading("d", text=f"PM {r['tipos'][-1]}")
        filas = [[f["mes"].strftime("%m-%Y"), *f["cuenta"], f["total"], f["detalle"]] for f in r["filas"]]
        e = self.m.estado(eq)
        filas.append(["Total período", *r["total"], sum(r["total"]),
                      f"Primera PM: PM {fmt_tipo(e['sugerido'])}" if e["n"] else "-"])
        llenar(self.tv_pm, filas, [""] * 6 + ["total"])
        llenar(self.tv_pl, [[x["k"], f"PM {fmt_tipo(x['tipo'])}", x["horo"], x["fecha"],
                             f"S{x['fecha'].isocalendar()[1]:02d}", ""] for x in r["proyeccion"]])

    # ------------------------------------------------------ PROYECCIÓN ACEITES
    def _tab_proy_aceites(self, tab):
        d = Desplazable(tab)
        d.pack(fill="both", expand=True)
        p = d.interior
        s1 = self._seccion(p, "1. PERÍODO A PROYECTAR")
        s1.pack(fill="x", pady=4)
        self.var_desde = tk.StringVar()
        self.var_hasta = tk.StringVar()
        ttk.Label(s1, text="Desde (dd-mm-aaaa)").grid(row=0, column=0, sticky="w")
        ttk.Entry(s1, textvariable=self.var_desde, width=12).grid(row=0, column=1, padx=4)
        ttk.Label(s1, text="Hasta (dd-mm-aaaa)").grid(row=1, column=0, sticky="w")
        ttk.Entry(s1, textvariable=self.var_hasta, width=12).grid(row=1, column=1, padx=4)
        self._boton(s1, "Definir período", self._definir_periodo).grid(row=0, column=2, rowspan=2, padx=6)
        self._boton(s1, "Exportar", self._exportar_compra, "Verde").grid(row=0, column=3, rowspan=2, padx=6)
        self._boton(s1, "Aceites por semanas", lambda: self.nb.select(self.tabs["Aceites por semanas"]), "Naranja"
                    ).grid(row=0, column=4, rowspan=2, padx=6)
        self._boton(s1, "Kits a solicitar", lambda: self.nb.select(self.tabs["Kits a solicitar"]), "Morado"
                    ).grid(row=0, column=5, rowspan=2, padx=6)
        self.lbl_per = ttk.Label(s1, text="", style="Nota.TLabel", justify="left")
        self.lbl_per.grid(row=0, column=6, rowspan=2, padx=12, sticky="w")
        ttk.Label(s1, text="«Desde» a partir del 01-01-2023 y «Hasta» como máximo hoy + 60 meses. El tramo anterior a "
                           "hoy suma las PM ejecutadas del Historial; desde hoy, las PM proyectadas.",
                  style="Nota.TLabel").grid(row=2, column=0, columnspan=7, sticky="w", pady=(6, 0))
        self.s_pa2 = self._seccion(p, "2. COMPRA DEL PERÍODO")
        self.s_pa2.pack(fill="x", pady=4)
        self.pa2_marco = ttk.Frame(self.s_pa2)
        self.pa2_marco.pack(fill="x")
        self.s_pa3 = self._seccion(p, "3. RESUMEN POR AÑO DEL PERÍODO (litros sin margen; mes a mes en el Excel exportado)")
        self.s_pa3.pack(fill="x", pady=4)
        self.pa3_marco = ttk.Frame(self.s_pa3)
        self.pa3_marco.pack(fill="x")
        s4 = self._seccion(p, "4. PM DEL PERÍODO POR EQUIPO")
        s4.pack(fill="x", pady=4)
        m, self.tv_pa4 = tabla(s4, [("r", "Referencia", 200, "w"), *[(f"e{i}", "", 110, "center") for i in range(8)]],
                               height=7, stretch_last=False)
        m.pack(fill="x")
        self.s_pa5 = self._seccion(p, "5. CONSUMO POR MODELO DE FLOTA (informativo)")
        self.s_pa5.pack(fill="x", pady=4)
        self.pa5_marco = ttk.Frame(self.s_pa5)
        self.pa5_marco.pack(fill="x")

    def _periodo_actual(self):
        per = self.repo.get_config("periodos", {})
        f = lambda s: dt.date.fromisoformat(s) if s else None  # noqa: E731
        return f(per.get("desde")), f(per.get("hasta")), f(per.get("sem_ini")), per.get("sem_n") or 4

    def _reemplazar_tabla(self, marco, columnas, filas, tags=None, height=None):
        for w in marco.winfo_children():
            w.destroy()
        m, tv = tabla(marco, columnas, height=height or len(filas), stretch_last=False)
        m.pack(fill="x")
        llenar(tv, filas, tags)
        return tv

    def _refrescar_proy_aceites(self):
        d1, d2, _, _ = self._periodo_actual()
        per = self.m.periodo(d1, d2)
        self._per = per
        self.var_desde.set(fmt_fecha(per["ini"]))
        self.var_hasta.set(fmt_fecha(per["fin"]))
        self.lbl_per.configure(text=f"Período: {fmt_fecha(per['ini'])} al {fmt_fecha(per['fin'])} "
                                    f"({fmt_num(per['dias'])} días)\n{self.m.texto_tramos(per['ini'], per['fin'])}")
        m = self.m
        self.s_pa2.configure(text=f"2. COMPRA DEL PERÍODO {fmt_fecha(per['ini'])} AL {fmt_fecha(per['fin'])} · "
                                  "FLOTA COMPLETA (litros)")
        eqs = per["equipos"]
        cols = [("p", "N° parte", 70, "w"), ("n", "Lubricante", 220, "w"), *[(f"q{i}", e, 70, "center")
                                                                            for i, e in enumerate(eqs)],
                ("ej", "Ejecutado (L)", 90, "center"), ("pr", "Proyectado (L)", 95, "center"),
                ("t", "Total período (L)", 105, "center"), ("mg", f"Margen {fmt_pct(m.p['margen'])} (L)", 90, "center"),
                ("cm", "Total con margen (L)", 120, "center"), ("ta", f"Tarros ({fmt_tipo(m.p['tarro'])} L)", 100, "center"),
                ("so", "Litros sobrantes", 110, "center")]
        filas = [[f["parte"], f["nombre"], *f["por_eq"], f["ejec"], f["proy"], f["total"], f["margen"], f["con_margen"],
                  f["tarros"], f["sobrante"]] for f in per["filas"]]
        tot = ["TOTAL", ""] + [sum(r[i] for r in filas) for i in range(2, len(cols))]
        npm = ["", "N° de PM", *per["n_pm"], per["n_ej_total"], per["n_pr_total"], per["n_ej_total"] + per["n_pr_total"],
               "", "", "", ""]
        self._reemplazar_tabla(self.pa2_marco, cols, filas + [tot, npm], [""] * len(filas) + ["total", "total"])
        partes = per["partes"]
        cols = [("a", "Año", 70, "w"), ("e", "PM ejecutadas", 100, "center"), ("p", "PM proyectadas", 105, "center"),
                *[(f"l{i}", pt, 85, "center") for i, pt in enumerate(partes)], ("t", "Total litros", 100, "center")]
        filas = [[str(a["ano"]), a["n_ej"], a["n_pr"], *[a["litros"][pt] for pt in partes], a["total"]] for a in per["anos"]]
        filas.append(["TOTAL"] + [sum(r[i] for r in filas) for i in range(1, len(cols))])
        self._reemplazar_tabla(self.pa3_marco, cols, filas, [""] * (len(filas) - 1) + ["total"])
        tv = self.tv_pa4
        for i in range(8):
            tv.heading(f"e{i}", text=eqs[i] if i < len(eqs) else "")
        pe = per["por_equipo"]
        rel = lambda f: [f(x) for x in pe] + [""] * (8 - len(pe))  # noqa: E731
        llenar(tv, [["Modelo", *rel(lambda x: x["modelo"])],
                    ["Horómetro de hoy", *rel(lambda x: fmt_num(x["horo_hoy"]))],
                    ["PM actual", *rel(lambda x: f"PM {fmt_tipo(x['pm_actual'])}")],
                    ["PM ejecutadas en el período", *rel(lambda x: x["n_ej"])],
                    ["PM proyectadas en el período", *rel(lambda x: x["n_pr"])],
                    ["Consumo diario (L/día)", *rel(lambda x: x["tasa"])],
                    ["Proyección cubre hasta", *rel(lambda x: fmt_fecha(x["cubre"]) or "-")]])
        self.s_pa5.configure(text=f"5. CONSUMO POR MODELO DE FLOTA · {fmt_fecha(per['ini'])} AL {fmt_fecha(per['fin'])}"
                                  f" · CON MARGEN {fmt_pct(m.p['margen'])} (informativo)")
        pm = per["por_modelo"]
        cols = [("p", "N° parte", 70, "w"), ("n", "Lubricante", 220, "w")]
        for i, x in enumerate(pm):
            eqtxt = " + ".join(x["equipos"])
            cols += [(f"l{i}", f"{x['modelo']} ({eqtxt})\nLitros período", 150, "center"),
                     (f"c{i}", "Con margen", 90, "center"), (f"t{i}", "Tarros", 70, "center")]
        cols += [("tc", "Total con margen", 120, "center"), ("tt", "Tarros flota", 90, "center")]
        filas = []
        for f in per["filas"]:
            pt = f["parte"]
            fila = [pt, f["nombre"]]
            for x in pm:
                fila += [x["litros"][pt], x["con_margen"][pt], x["tarros"][pt]]
            fila += [sum(x["con_margen"][pt] for x in pm), sum(x["tarros"][pt] for x in pm)]
            filas.append(fila)
        filas.append(["TOTAL", ""] + [sum(r[i] for r in filas) for i in range(2, len(cols))])
        filas.append(["", "N° de PM en el período"] + sum(([x["n_pm"], "", ""] for x in pm), []) + ["", ""])
        self._reemplazar_tabla(self.pa5_marco, cols, filas, [""] * (len(filas) - 2) + ["total", "total"])

    def _definir_periodo(self):
        if self.acc.definir_periodo(self.var_desde.get(), self.var_hasta.get()):
            self.refrescar()

    def _exportar_compra(self):
        d1, d2, _, _ = self._periodo_actual()
        if not d1 or not d2:
            self.ui.aviso("Primero defina el período con «Definir período».")
            return
        msg = self.acc.validar_desde(d1) or self.acc.validar_periodo(d1, d2)
        if msg:
            self.ui.aviso(f"{msg}\n\nCorrija el período con «Definir período».")
            return
        ruta = self._guardar_como(f"Compra_aceites_{d1:%d-%m-%Y}_al_{d2:%d-%m-%Y}.xlsx", "Exportar compra de aceites")
        if not ruta:
            return
        try:
            r = exportar.exportar_compra(self.m, d1, d2, ruta, self.acc.usuario(), self.ruta_db.name)
        except Exception as ex:
            self._error_export(ex)
            return
        per = r["per"]
        msg = (f"Compra exportada:\n{ruta}\n\nPeríodo {fmt_fecha(d1)} al {fmt_fecha(d2)}: "
               f"{fmt_num(per['total_con_margen'])} L con margen · {per['total_tarros']} tarros · {r['n_pm']} PM.")
        if r["aviso"]:
            msg += f"\n\n{r['aviso']}"
        self._tras_exportar(msg, ruta)

    # ---------------------------------------------------- ACEITES POR SEMANAS
    def _tab_semanas(self, tab):
        d = Desplazable(tab)
        d.pack(fill="both", expand=True)
        p = d.interior
        s1 = self._seccion(p, "1. PLAZO EN SEMANAS")
        s1.pack(fill="x", pady=4)
        self.var_sini = tk.StringVar()
        self.var_sn = tk.StringVar()
        ttk.Label(s1, text="Fecha de inicio (dd-mm-aaaa)").grid(row=0, column=0, sticky="w")
        ttk.Entry(s1, textvariable=self.var_sini, width=12).grid(row=0, column=1, padx=4)
        ttk.Label(s1, text="N° de semanas (1 a 52)").grid(row=1, column=0, sticky="w")
        ttk.Entry(s1, textvariable=self.var_sn, width=6).grid(row=1, column=1, padx=4, sticky="w")
        self._boton(s1, "Calcular", self._calcular_semanas).grid(row=0, column=2, rowspan=2, padx=6)
        self._boton(s1, "Exportar", self._exportar_semanas, "Verde").grid(row=0, column=3, rowspan=2, padx=6)
        self._boton(s1, "Kits a solicitar", lambda: self.nb.select(self.tabs["Kits a solicitar"]), "Morado"
                    ).grid(row=0, column=4, rowspan=2, padx=6)
        self.lbl_sem = ttk.Label(s1, text="", style="Nota.TLabel")
        self.lbl_sem.grid(row=0, column=5, rowspan=2, padx=12, sticky="w")
        ttk.Label(s1, text="Desde el 01-01-2023. Hasta hoy se cuentan las PM ejecutadas (Historial); desde hoy, las "
                           "proyectadas. Cada semana son 7 días desde la fecha de inicio.", style="Nota.TLabel"
                  ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
        self.s_sw2 = self._seccion(p, "2. ACEITES DEL PLAZO")
        self.s_sw2.pack(fill="x", pady=4)
        self.sw2_marco = ttk.Frame(self.s_sw2)
        self.sw2_marco.pack(fill="x")
        s3 = self._seccion(p, "3. SEMANA A SEMANA (litros sin margen · PM de cada equipo en la semana; «(ejec.)» = "
                              "registrada en el Historial)")
        s3.pack(fill="x", pady=4)
        self.sw3_marco = ttk.Frame(s3)
        self.sw3_marco.pack(fill="x")

    def _refrescar_semanas(self):
        _, _, ini, n = self._periodo_actual()
        s = self.m.semanas(ini, n)
        self._sem = s
        self.var_sini.set(fmt_fecha(s["ini"]))
        self.var_sn.set(str(s["n"]))
        self.lbl_sem.configure(text=f"Plazo: {fmt_fecha(s['ini'])} al {fmt_fecha(s['fin'])} ({s['n']} semana(s), "
                                    f"{s['dias']} días)")
        m = self.m
        eqs = s["equipos"]
        self.s_sw2.configure(text=f"2. ACEITES DEL PLAZO {fmt_fecha(s['ini'])} AL {fmt_fecha(s['fin'])} "
                                  "(PM ejecutadas hasta hoy + proyectadas)")
        cols = [("p", "N° parte", 70, "w"), ("n", "Lubricante", 220, "w"),
                *[(f"q{i}", e, 75, "center") for i, e in enumerate(eqs)], ("t", "Total plazo (L)", 100, "center"),
                ("mg", f"Margen {fmt_pct(m.p['margen'])} (L)", 90, "center"), ("cm", "Total con margen (L)", 120, "center"),
                ("ta", f"Tarros ({fmt_tipo(m.p['tarro'])} L)", 90, "center"), ("so", "Litros sobrantes", 100, "center")]
        filas = [[f["parte"], f["nombre"], *f["por_eq"], f["total"], f["margen"], f["con_margen"], f["tarros"],
                  f["sobrante"]] for f in s["filas"]]
        tot = ["TOTAL", ""] + [sum(r[i] for r in filas) for i in range(2, len(cols))]
        npm = ["", "N° de PM", *s["n_pm"], s["n_pm_total"], "", "", "", ""]
        self._reemplazar_tabla(self.sw2_marco, cols, filas + [tot, npm], [""] * len(filas) + ["total", "total"])
        partes = s["partes"]
        cols = [("s", "Semana", 60, "center"), ("p", "Período", 150, "w"), ("i", "Sem. ISO", 70, "center"),
                *[(f"e{i}", e, 160, "w") for i, e in enumerate(eqs)], ("n", "N° PM", 60, "center"),
                *[(f"l{i}", pt, 75, "center") for i, pt in enumerate(partes)], ("t", "Total (L)", 85, "center")]
        filas = [["TOTAL", "", "", *[f"{v} PM" for v in s["n_pm"]],
                  sum(w["n_pm"] for w in s["semanas"]),
                  *[sum(w["litros"][pt] for w in s["semanas"]) for pt in partes], sum(w["total"] for w in s["semanas"])]]
        for w in s["semanas"]:
            filas.append([w["sem"], w["periodo"], w["iso"], *w["celdas"], w["n_pm"], *[w["litros"][pt] for pt in partes],
                          w["total"]])
        self._reemplazar_tabla(self.sw3_marco, cols, filas, ["total"] + [""] * len(s["semanas"]),
                               height=min(len(filas), 30))

    def _calcular_semanas(self):
        if self.acc.definir_semanas(self.var_sini.get(), self.var_sn.get()):
            self.refrescar()

    def _exportar_semanas(self):
        _, _, ini, n = self._periodo_actual()
        if not ini:
            self.ui.aviso("Primero defina el plazo con «Calcular».")
            return
        ruta = self._guardar_como(f"Aceites_{n}_semanas_desde_{ini:%d-%m-%Y}.xlsx", "Exportar aceites por semanas")
        if not ruta:
            return
        try:
            r = exportar.exportar_semanas(self.m, ini, n, ruta, self.acc.usuario(), self.ruta_db.name)
        except Exception as ex:
            self._error_export(ex)
            return
        s = r["sem"]
        msg = (f"Aceites por semanas exportado:\n{ruta}\n\nPlazo {fmt_fecha(s['ini'])} al {fmt_fecha(s['fin'])}: "
               f"{fmt_num(s['total_con_margen'])} L con margen · {s['total_tarros']} tarros · {r['n_pm']} PM.")
        if r["aviso"]:
            msg += f"\n\n{r['aviso']}"
        self._tras_exportar(msg, ruta)

    # -------------------------------------------------------- KITS A SOLICITAR
    def _tab_kits_sol(self, tab):
        d = Desplazable(tab)
        d.pack(fill="both", expand=True)
        p = d.interior
        ttk.Label(p, text="KITS A SOLICITAR", style="Titulo.TLabel").pack(anchor="w")
        self.lbl_ks = ttk.Label(p, text="", style="Nota.TLabel", justify="left")
        self.lbl_ks.pack(anchor="w")
        b = ttk.Frame(p)
        b.pack(anchor="w", pady=4)
        self._boton(b, "Proyección aceites", lambda: self.nb.select(self.tabs["Proyección aceites"]), "Naranja"
                    ).pack(side="left")
        self._boton(b, "Aceites por semanas", lambda: self.nb.select(self.tabs["Aceites por semanas"]), "Naranja"
                    ).pack(side="left", padx=6)
        s1 = self._seccion(p, "1. PM POR EQUIPO (período por fechas: solo proyectadas · plazo en semanas: ejecutadas + "
                              "proyectadas)")
        s1.pack(fill="x", pady=4)
        self.ks1_marco = ttk.Frame(s1)
        self.ks1_marco.pack(fill="x")
        s2 = self._seccion(p, "2. KITS A SOLICITAR (1 kit por PM)")
        s2.pack(fill="x", pady=4)
        self.ks2_marco = ttk.Frame(s2)
        self.ks2_marco.pack(fill="x")
        s3 = self._seccion(p, "3. REPUESTOS SUELTOS (adicionales, pedir por separado y tomar de bodega)")
        s3.pack(fill="x", pady=4)
        self.ks3_marco = ttk.Frame(s3)
        self.ks3_marco.pack(fill="x")

    def _refrescar_kits_sol(self):
        per, sem, m = self._per, self._sem, self.m
        ks = m.kits_solicitar(per, sem)
        self.lbl_ks.configure(text=f"Período por fechas: {fmt_fecha(per['ini'])} al {fmt_fecha(per['fin'])}   ·   "
                                   f"Plazo en semanas: {fmt_fecha(sem['ini'])} al {fmt_fecha(sem['fin'])} "
                                   f"({sem['n']} semana(s)).\nUn kit por PM según modelo y tipo. Repuestos sueltos = "
                                   "cantidad por PM de «Kits PM» × N° de PM.")
        filas = []
        for eq in m.lista_equipos():
            mod = m.modelo_de(eq)
            tipos = [250, 500, 1000, 2000 if mod == "DR412i" else 1500]
            a = [sum(1 for x in m.proyeccion(eq) if x["tipo"] == t and per["ini"] <= x["fecha"] <= per["fin"])
                 for t in tipos]
            b = [sum(1 for x in sem["proyectadas"] if x["equipo"] == eq and x["tipo"] == t)
                 + sum(1 for f in m.ejecutadas_en(sem["ini"], sem["fin_ej"], eq) if f["tipo"] == t) for t in tipos]
            filas.append([eq, mod, *a, sum(a), *b, sum(b)])
        filas.append(["TOTAL", ""] + [sum(r[i] for r in filas) for i in range(2, 12)])
        cols = [("e", "Equipo", 60, "center"), ("m", "Modelo", 70, "center")]
        for pre in ("Fechas", "Semanas"):
            cols += [(f"{pre}a", f"{pre}: PM 250", 100, "center"), (f"{pre}b", "PM 500", 70, "center"),
                     (f"{pre}c", "PM 1000", 70, "center"), (f"{pre}d", "PM 1500/2000", 95, "center"),
                     (f"{pre}t", "Total", 60, "center")]
        self._reemplazar_tabla(self.ks1_marco, cols, filas, [""] * (len(filas) - 1) + ["total"])
        filas = [[k["kit"], k["etiqueta"], k["equipos"], k["ubic"], k["n_per"], k["n_sem"]] for k in ks["kits"]]
        filas.append(["TOTAL KITS", "", "", "", sum(k["n_per"] for k in ks["kits"]), sum(k["n_sem"] for k in ks["kits"])])
        self._reemplazar_tabla(self.ks2_marco, [("k", "N° de kit", 110, "w"), ("m", "Modelo · PM", 130, "w"),
                                                ("e", "Equipos", 130, "w"), ("u", "Ubicación del kit", 120, "center"),
                                                ("p", "Período por fechas", 130, "center"),
                                                ("s", "Plazo en semanas", 130, "center")],
                               filas, [""] * (len(filas) - 1) + ["total"])
        filas = [[r["np"], r["ubic"], r["origen"], r["n_per"], r["n_sem"]] for r in ks["repuestos"]]
        filas.append(["TOTAL UNIDADES", "", "", sum(r["n_per"] for r in ks["repuestos"]),
                      sum(r["n_sem"] for r in ks["repuestos"])])
        self._reemplazar_tabla(self.ks3_marco, [("n", "N° de parte", 110, "w"), ("u", "Ubicación", 100, "center"),
                                                ("o", "Origen (PM · tipo de repuesto · cantidad por PM)", 560, "w"),
                                                ("p", "Período por fechas", 130, "center"),
                                                ("s", "Plazo en semanas", 130, "center")],
                               filas, [""] * (len(filas) - 1) + ["total"], height=min(len(filas), 32))

    # ------------------------------------------------------------- KITS PM
    COLS_KITS = [("modelo", "Modelo", "txt", 70), ("tipo", "Tipo PM", "num", 60), ("cuadro", "Cuadro", "int", 55),
                 ("kit", "N° kit", "txt", 100), ("ubic_kit", "Ubicación kit", "txt", 90),
                 ("equipos", "Equipos", "txt", 150), ("linea", "Línea", "int", 50),
                 ("tipo_linea", "Tipo línea (SUB/KIT/ADIC)", "txt", 90), ("np", "N° de parte", "txt", 130),
                 ("cant", "Cantidad", "num", 65), ("ubic", "Ubicación", "txt", 80), ("com", "Comentario", "txt", 260)]

    def _tab_kits_pm(self, tab):
        ttk.Label(tab, text="KITS DE MANTENIMIENTO POR MODELO Y TIPO DE PM", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Fuente del cuadro «Kit de mantenimiento» del Panel y de «Kits a solicitar». Tipo línea: SUB = "
                            "subtítulo (línea 1 = contenido del kit), KIT = repuesto del kit, ADIC = repuesto suelto.",
                  style="Nota.TLabel").pack(anchor="w")
        b = ttk.Frame(tab)
        b.pack(fill="x", pady=6)
        self._boton(b, "Exportar listado", self._exportar_listado, "Verde").pack(side="left")
        self._boton(b, "Editar kits", lambda: self._editar_config("kits", "Kits PM", self.COLS_KITS)).pack(
            side="left", padx=6)
        self._boton(b, "Editar descripciones de repuestos",
                    lambda: self._editar_config("descripciones", "Descripciones repuestos",
                                                [("np", "N° de parte", "txt", 130),
                                                 ("descripcion", "Descripción", "txt", 400)])).pack(side="left")
        m, self.tv_kp = tabla(tab, [(k, t, a, "w") for k, t, _, a in self.COLS_KITS], height=26)
        m.pack(fill="both", expand=True)

    def _refrescar_kits_pm(self):
        llenar(self.tv_kp, [[k.get(c[0]) if c[0] not in ("tipo", "cuadro", "linea") else fmt_tipo(k.get(c[0]))
                             for c in self.COLS_KITS] for k in self.m.kits],
               ["kit" if k["tipo_linea"] == "SUB" else "" for k in self.m.kits])

    def _exportar_listado(self):
        ruta = self._guardar_como("Listado_repuestos_Kits_PM.xlsx", "Exportar listado de repuestos")
        if not ruta:
            return
        try:
            r = exportar.exportar_listado(self.m, ruta, self.ruta_db.name)
        except Exception as ex:
            self._error_export(ex)
            return
        self._tras_exportar(f"Listado exportado ({r['n_kits']} kits y {r['n_rep']} repuestos sin duplicados):\n{ruta}",
                            ruta)

    # ---------------------------------------------------- LECTURAS / PROGRAM.
    def _tab_lecturas(self, tab):
        ttk.Label(tab, text="LECTURAS DE HORÓMETRO", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Se actualizan al abrir el programa y con «Actualizar horómetro».", style="Nota.TLabel"
                  ).pack(anchor="w")
        m, self.tv_lec = tabla(tab, [("e", "Equipo", 80, "center"), ("h", "Horómetro (h)", 110, "center"),
                                     ("f", "Fecha lectura", 110, "center"), ("p", "Registrado por", 200, "w")], height=7)
        m.pack(fill="x", pady=6)
        ttk.Label(tab, text="PROGRAMACIÓN", style="Titulo.TLabel").pack(anchor="w", pady=(12, 0))
        ttk.Label(tab, text="Se actualiza con «Programar PM» y se limpia al registrar la PM ejecutada.",
                  style="Nota.TLabel").pack(anchor="w")
        m, self.tv_prog = tabla(tab, [("e", "Equipo", 80, "center"), ("t", "PM programada", 110, "center"),
                                      ("h", "Horómetro objetivo", 130, "center"), ("f", "Fecha programada", 120, "center"),
                                      ("a", "Actualizado el", 140, "center")], height=7)
        m.pack(fill="x", pady=6)

    def _refrescar_lecturas(self):
        m = self.m
        llenar(self.tv_lec, [[eq, (m.lecturas.get(eq) or {}).get("horo"), (m.lecturas.get(eq) or {}).get("fecha"),
                              (m.lecturas.get(eq) or {}).get("por")] for eq in m.lista_equipos()])
        llenar(self.tv_prog, [[eq, fmt_tipo(p.get("tipo")) if es_num(p.get("tipo")) else "", p.get("horo_obj"),
                               p.get("fecha"), fmt_fechahora(p.get("actualizado"))]
                              for eq in m.lista_equipos() for p in [m.prog.get(eq) or {}]])

    # ---------------------------------------------------------- CONFIGURACIÓN
    def _tab_config(self, tab):
        d = Desplazable(tab)
        d.pack(fill="both", expand=True)
        p = d.interior
        ttk.Label(p, text="CONFIGURACIÓN DEL SISTEMA", style="Titulo.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        s1 = self._seccion(p, "Parámetros")
        s1.grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        self.vars_param = {}
        for i, (k, tit, _) in enumerate(PARAMS_DEF):
            ttk.Label(s1, text=tit).grid(row=i, column=0, sticky="w", pady=1)
            v = tk.StringVar()
            ttk.Entry(s1, textvariable=v, width=10).grid(row=i, column=1, sticky="w", padx=6)
            self.vars_param[k] = v
        i = len(PARAMS_DEF)
        ttk.Label(s1, text="Usuario que registra (vacío = usuario de Windows)").grid(row=i, column=0, sticky="w", pady=1)
        v = tk.StringVar()
        ttk.Entry(s1, textvariable=v, width=24).grid(row=i, column=1, sticky="w", padx=6)
        self.vars_param["usuario"] = v
        ttk.Label(s1, text="Porcentajes como decimal (0,15 = 15 %).", style="Nota.TLabel").grid(
            row=i + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self._boton(s1, "Guardar parámetros", self._guardar_params, "Verde").grid(row=i + 2, column=0, sticky="w",
                                                                                 pady=(8, 0))
        s2 = self._seccion(p, "Tablas de configuración")
        s2.grid(row=1, column=1, sticky="nw", padx=4, pady=4)
        tablas = [
            ("equipos", "Equipos", [("equipo", "Equipo", "txt", 80), ("modelo", "Modelo", "txt", 90),
                                    ("faena", "Faena", "txt", 80)], ""),
            ("ciclos", "Ciclo de PM mayores por modelo",
             [("modelo", "Modelo", "txt", 90), ("pos1", "Pos. 1", "num", 60), ("pos2", "Pos. 2", "num", 60),
              ("pos3", "Pos. 3", "num", 60), ("pos4", "Pos. 4", "num", 60), ("largo", "N° posiciones", "int", 90),
              ("cierres", "Tipos que cierran ciclo (separados por coma)", "txt", 220)],
             "Entre cada PM mayor del ciclo se ejecuta una PM 250."),
            ("tipos", "Tipos de PM válidos por modelo",
             [("modelo", "Modelo", "txt", 90), ("tipos", "Tipos (separados por coma)", "txt", 250)], ""),
            ("aceites_cfg", "Aceites por modelo",
             [("modelo", "Modelo", "txt", 80), ("componente", "Componente", "txt", 220),
              ("frecuencia", "Frecuencia (h)", "num", 90), ("texto", "Texto «Frecuencia de cambio»", "txt", 220)],
             "Un aceite se reinicia en toda PM de tipo mayor o igual a su frecuencia."),
            ("consumo", "Consumo de lubricantes por PM",
             [("modelo", "Modelo", "txt", 70), ("sistema", "Sistema", "txt", 200), ("lubricante", "Lubricante", "txt", 180),
              ("parte", "N° parte", "txt", 70), ("litros", "Litros", "num", 60)]
             + [(str(t), str(t), "num", 50) for t in self.m.consumo_tipos],
             "Marque 1 en los tipos de PM que consumen el lubricante; 0 o vacío = no consume."),
            ("diario", "Consumo diario por equipo",
             [("equipo", "Equipo", "txt", 70), ("parte", "N° parte", "txt", 80), ("lubricante", "Lubricante", "txt", 200),
              ("litros_dia", "Litros por día", "num", 90)],
             "Se multiplica por los días calendario del período (incluye días sin operación)."),
        ]
        for i, (clave, tit, cols, nota) in enumerate(tablas):
            self._boton(s2, tit, lambda c=clave, t=tit, cs=cols, n=nota: self._editar_config(c, t, cs, n)
                        ).grid(row=i, column=0, sticky="ew", pady=2)
        s3 = self._seccion(p, "Datos")
        s3.grid(row=2, column=0, columnspan=2, sticky="nw", padx=4, pady=4)
        ttk.Label(s3, text=f"Base de datos: {self.ruta_db}", style="Nota.TLabel").grid(row=0, column=0, columnspan=4,
                                                                                    sticky="w")
        self._boton(s3, "Respaldar base de datos", self._respaldar, "Verde").grid(row=1, column=0, pady=6, sticky="w")
        self._boton(s3, "Importar formatos de solicitud desde Excel", self._importar_formatos).grid(
            row=1, column=1, padx=6, sticky="w")
        self._boton(s3, "Reimportar todo desde Excel (reemplaza los datos)", self._reimportar, "Rojo").grid(
            row=1, column=2, sticky="w")

    def _refrescar_config(self):
        p = self.m.p
        for k, v in self.vars_param.items():
            x = p.get(k, "")
            self.vars_param[k].set(fmt_tipo(x).replace(".", ",") if es_num(x) else (x or ""))

    def _guardar_params(self):
        nuevo = dict(self.m.p)
        for k, tit, _ in PARAMS_DEF:
            n = parse_num(self.vars_param[k].get())
            if n is None:
                self.ui.aviso(f"«{tit}» debe ser numérico.")
                return
            nuevo[k] = n
        if nuevo["intervalo"] <= 0 or nuevo["horas_dia"] <= 0 or nuevo["tarro"] <= 0:
            self.ui.aviso("El intervalo, las horas/día y los litros por tarro deben ser mayores que cero.")
            return
        nuevo["usuario"] = self.vars_param["usuario"].get().strip()
        self.repo.set_config("params", nuevo)
        self.refrescar()
        self.ui.info("Parámetros guardados.")

    def _editar_config(self, clave, titulo, cols, nota=""):
        def guardar(filas):
            for f in filas:
                for k, _, tipo, _ in cols:
                    if tipo in ("num", "int") and f.get(k) in ("", None) and clave in ("consumo",):
                        f[k] = 0.0
                if clave == "kits":
                    f["tipo_linea"] = str(f.get("tipo_linea") or "").upper()
            self.repo.set_config(clave, filas)
            self.m.recargar()
            if clave in ("ciclos", "equipos"):
                self.acc.reparar_claves(silencioso=True)
            self.refrescar()
        EditorTabla(self, titulo, cols, self.repo.get_config(clave, []), guardar, nota)

    def _respaldar(self):
        ruta = filedialog.asksaveasfilename(parent=self, title="Respaldar base de datos",
                                            initialfile=f"PlanificacionPM_respaldo_{dt.datetime.now():%Y-%m-%d_%H%M}.db",
                                            defaultextension=".db", filetypes=[("Base de datos", "*.db")])
        if not ruta:
            return
        self.repo.cx.commit()
        destino = __import__("sqlite3").connect(ruta)
        with destino:
            self.repo.cx.backup(destino)
        destino.close()
        self.ui.info(f"Respaldo guardado en:\n{ruta}")

    def _importar_formatos(self):
        ruta = filedialog.askopenfilename(parent=self, title="Libro con las hojas «Formato <modelo>»",
                                          filetypes=[("Libro de Excel", "*.xlsm *.xlsx")])
        if not ruta:
            return
        try:
            nombres = openpyxl.load_workbook(ruta, read_only=True).sheetnames
            n = 0
            with self.repo.transaccion():
                for hoja in nombres:
                    if hoja.startswith("Formato "):
                        self.repo.set_plantilla(hoja[len("Formato "):].strip(), extraer_hoja(Path(ruta), hoja))
                        n += 1
        except Exception as ex:
            self.ui.error(f"No fue posible importar los formatos.\nDetalle: {ex}")
            return
        self.ui.info(f"{n} formato(s) importado(s)." if n else "El libro no tiene hojas «Formato <modelo>».")

    def _reimportar(self):
        if not messagebox.askyesno(TITULO, "Se reemplazarán TODOS los datos (Historial, aceites, lecturas, "
                                           "programación y configuración) por los del libro Excel elegido.\n\n"
                                           "Se creará un respaldo automático antes. ¿Continuar?", icon="warning",
                                   default=messagebox.NO, parent=self):
            return
        ruta = filedialog.askopenfilename(parent=self, title="Libro Excel a importar",
                                          filetypes=[("Libro de Excel", "*.xlsm *.xlsx")])
        if not ruta:
            return
        self.repo.cx.commit()
        resp = self.ruta_db.with_name(f"{self.ruta_db.stem}_antes_de_importar_{dt.datetime.now():%Y%m%d_%H%M%S}.db")
        shutil.copy2(self.ruta_db, resp)
        try:
            r = importar_libro(ruta, self.repo)
        except Exception as ex:
            self.ui.error(f"No fue posible importar el libro (los datos no cambiaron).\nDetalle: {ex}")
            return
        self.m.recargar()
        self.cb_eq.configure(values=self.m.lista_equipos())
        self.refrescar()
        self.ui.info(f"Importación terminada: {r.get('historial', 0)} PM y {r.get('aceites', 0)} registros de aceite.\n"
                     f"Respaldo previo: {resp}")

    # ------------------------------------------------------------ INSTRUCCIONES
    def _tab_instrucciones(self, tab):
        from .instrucciones import TEXTO
        t = tk.Text(tab, wrap="word", font=("Segoe UI", 10), padx=12, pady=12, borderwidth=0)
        sy = ttk.Scrollbar(tab, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        t.pack(fill="both", expand=True)
        t.tag_configure("h", font=("Segoe UI", 11, "bold"), foreground=AZUL, spacing1=10)
        for linea in TEXTO.strip().splitlines():
            t.insert("end", linea.lstrip("#").strip() + "\n", ("h",) if linea.startswith("#") else ())
        t.configure(state="disabled")

    # ---------------------------------------------------------------- refresco
    def refrescar(self, solo_calculo=False):
        self.m.recargar()
        eqs = self.m.lista_equipos()
        if self.eq not in eqs and eqs:
            self.var_eq.set(eqs[0])
        if solo_calculo:
            return
        for cb in (self.cb_fh, self.cb_fa):
            cb.configure(values=["Todos", *eqs])
        for nombre, fn in (("Panel", self._refrescar_panel), ("Historial", self._refrescar_historial),
                           ("Aceites", self._refrescar_aceites), ("Proyección", self._refrescar_proyeccion),
                           ("Proyección aceites", self._refrescar_proy_aceites),
                           ("Aceites por semanas", self._refrescar_semanas), ("Kits a solicitar", self._refrescar_kits_sol),
                           ("Kits PM", self._refrescar_kits_pm), ("Lecturas", self._refrescar_lecturas),
                           ("Configuración", self._refrescar_config)):
            try:
                fn()
            except Exception as ex:  # una sección con datos incoherentes no debe bloquear el resto
                messagebox.showerror(TITULO, f"Error al calcular «{nombre}».\nDetalle: {ex}", parent=self)


def main():
    App().mainloop()
