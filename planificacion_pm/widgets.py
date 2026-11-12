"""Componentes de interfaz reutilizables (Tkinter) con el tema de mantenimiento."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk

from . import TITULO, tema
from .tema import ACENTO, AMARILLO, BORDE, FONDO, FUENTE, NAVY, SUAVE, TARJETA, TEXTO
from .util import es_num, fmt_num, parse_num

AZUL = NAVY
AZUL_CLARO = "#E3EAF3"
ROJO = tema.ROJO
VERDE = tema.VERDE
NARANJA = ACENTO


def tabla(parent, columnas, height=8, stretch_last=True):
    """Treeview con barras de desplazamiento. columnas: [(id, titulo, ancho, anchor)]."""
    marco = ttk.Frame(parent)
    ids = [c[0] for c in columnas]
    tv = ttk.Treeview(marco, columns=ids, show="headings", height=height)
    for i, (cid, tit, ancho, anc) in enumerate(columnas):
        tv.heading(cid, text=tit)
        tv.column(cid, width=ancho, anchor=anc, stretch=(stretch_last and i == len(columnas) - 1))
    sy = ttk.Scrollbar(marco, orient="vertical", command=tv.yview)
    sx = ttk.Scrollbar(marco, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    tv.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    marco.rowconfigure(0, weight=1)
    marco.columnconfigure(0, weight=1)
    tv.tag_configure("par", background="#F5F8FB")
    tv.tag_configure("total", background="#E3EAF3", foreground=NAVY, font=(FUENTE, 9, "bold"))
    tv.tag_configure("rojo", background="#FADBD8", foreground="#8E1B1B")
    tv.tag_configure("amarillo", background="#FFF1CC", foreground="#7A5200")
    tv.tag_configure("verde", background="#DFF3E6", foreground="#1D6B3D")
    tv.tag_configure("kit", background="#FDEBD8", foreground="#8A4A0E", font=(FUENTE, 9, "bold"))
    tv.tag_configure("gris", foreground="#7F7F7F")
    return marco, tv


def llenar(tv, filas, tags=None):
    tv.delete(*tv.get_children())
    for i, f in enumerate(filas):
        t = tags[i] if tags else ""
        if not t:
            t = "par" if i % 2 else ""
        tv.insert("", "end", values=[_txt(v) for v in f], tags=t if isinstance(t, tuple) else ((t,) if t else ()))


def _txt(v):
    if v is None:
        return ""
    if es_num(v):
        return fmt_num(v)
    if hasattr(v, "strftime"):
        return v.strftime("%d-%m-%Y")
    return str(v)


class Seccion(ttk.Frame):
    """Tarjeta blanca con ícono y título. Los hijos se ubican con grid o pack como en un marco normal."""

    def __init__(self, parent, titulo, icono="herramientas", **kw):
        super().__init__(parent, style="Card.TFrame", padding=(14, 46, 14, 12), **kw)
        cab = ttk.Frame(self)
        self._img = tema.icono(self, icono, 18, ACENTO)
        ttk.Label(cab, image=self._img).pack(side="left", padx=(0, 8))
        self._lbl = ttk.Label(cab, text=titulo, style="SecTitulo.TLabel")
        self._lbl.pack(side="left")
        cab.place(x=14, y=12, bordermode="outside")
        linea = tk.Frame(self, height=2, background="#EEF1F5")
        linea.place(x=14, y=40, relwidth=1, width=-28, bordermode="outside")
        cab.lift()

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict) and "text" in cnf:
            kw["text"] = cnf.pop("text")
        if "text" in kw:
            self._lbl.configure(text=kw.pop("text"))
            if not kw and not cnf:
                return None
        return super().configure(cnf, **kw)

    config = configure


class Tarjeta(tk.Frame):
    """Indicador: título pequeño + valor grande, con franja de color según el estado."""

    def __init__(self, parent, titulo, ancho=18):
        super().__init__(parent, background=TARJETA, highlightthickness=1, highlightbackground=BORDE)
        self.franja = tk.Frame(self, width=5, background="#C9D3DE")
        self.franja.pack(side="left", fill="y")
        cuerpo = tk.Frame(self, background=TARJETA, padx=10, pady=6)
        cuerpo.pack(side="left", fill="both", expand=True)
        self.lbl = tk.Label(cuerpo, text=titulo, background=TARJETA, foreground=SUAVE, font=(FUENTE, 8),
                            wraplength=ancho * 8, justify="left", anchor="w")
        self.lbl.pack(anchor="w", fill="x")
        self.val = tk.Label(cuerpo, text="", background=TARJETA, foreground=TEXTO, font=(FUENTE, 12, "bold"),
                            wraplength=ancho * 9, justify="left", anchor="w")
        self.val.pack(anchor="w", fill="x")
        cuerpo.bind("<Configure>", self._ajustar)

    def _ajustar(self, e):
        w = max(60, e.width - 22)
        self.lbl.configure(wraplength=w)
        self.val.configure(wraplength=w)

    def set(self, valor, color=None, titulo=None):
        txt = _txt(valor)
        largo = max((len(w) for w in txt.split()), default=0)
        self.val.configure(text=txt, foreground=color or TEXTO,
                           font=(FUENTE, 12 if largo <= 9 else 10, "bold"))
        self.franja.configure(background=color or "#C9D3DE")
        if titulo is not None:
            self.lbl.configure(text=titulo)


class Medidor(tk.Canvas):
    """Medidor circular (horas usadas del intervalo de PM)."""

    def __init__(self, parent, tam=190):
        super().__init__(parent, width=tam, height=tam, background=TARJETA, highlightthickness=0)
        self.tam = tam

    def dibujar(self, valor, maximo, color, grande, chico, pie=""):
        self.delete("all")
        t, g = self.tam, 18
        caja = (g, g, t - g, t - g)
        self.create_arc(caja, start=-60, extent=300, style="arc", width=g, outline="#E6EBF1")
        frac = 0 if not maximo else max(0.0, min(1.0, valor / maximo))
        if frac > 0:
            self.create_arc(caja, start=240, extent=-300 * frac, style="arc", width=g, outline=color)
        for k in range(11):
            a = math.radians(240 - 30 * k)
            r1, r2 = t / 2 - g - 6, t / 2 - g - (14 if k % 5 == 0 else 10)
            c = t / 2
            self.create_line(c + r1 * math.cos(a), c - r1 * math.sin(a), c + r2 * math.cos(a), c - r2 * math.sin(a),
                             fill="#B8C3CF", width=2)
        self.create_text(t / 2, t / 2 - 8, text=grande, fill=color, font=(FUENTE, 22, "bold"))
        self.create_text(t / 2, t / 2 + 22, text=chico, fill=SUAVE, font=(FUENTE, 9), width=t - 70, justify="center")
        if pie:
            self.create_text(t / 2, t - 10, text=pie, fill=TEXTO, font=(FUENTE, 9, "bold"))


class VidaAceites(tk.Canvas):
    """Barras de vida útil de cada aceite: horas acumuladas sobre su frecuencia de cambio."""

    ALTO = 30

    def __init__(self, parent):
        super().__init__(parent, background=TARJETA, highlightthickness=0, height=200)
        self._filas = []
        self.bind("<Configure>", lambda _e: self._dibujar())

    def dibujar(self, filas):
        self._filas = filas
        self.configure(height=max(60, len(filas) * self.ALTO + 30))
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        w = max(self.winfo_width(), 560)
        x_bar, w_txt, w_est = 210, 150, 120
        w_bar = max(80, w - x_bar - w_txt - w_est - 10)
        y = 6
        self.create_text(4, y + 6, text="Componente", anchor="w", fill=SUAVE, font=(FUENTE, 8, "bold"))
        self.create_text(x_bar, y + 6, text="Vida útil del aceite (horas desde el último cambio / frecuencia)",
                         anchor="w", fill=SUAVE, font=(FUENTE, 8, "bold"))
        y += 22
        colores = {"Cambio vencido": tema.ROJO, "Cambio próximo": "#E0A100", "En condiciones": tema.VERDE}
        for i, a in enumerate(self._filas):
            if i % 2:
                self.create_rectangle(0, y - 2, w, y + self.ALTO - 4, fill="#F7F9FC", outline="")
            cy = y + (self.ALTO - 6) / 2
            self.create_text(4, cy, text=a["componente"], anchor="w", fill=TEXTO, font=(FUENTE, 9))
            col = colores.get(a["estado"], "#9AA6B2")
            self.create_rectangle(x_bar, cy - 7, x_bar + w_bar, cy + 7, fill="#E6EBF1", outline="")
            if es_num(a["acum"]) and a["frecuencia"]:
                frac = max(0.0, min(1.0, a["acum"] / a["frecuencia"]))
                if frac > 0:
                    self.create_rectangle(x_bar, cy - 7, x_bar + w_bar * frac, cy + 7, fill=col, outline="")
                txt = f"{fmt_num(a['acum'])} / {fmt_num(a['frecuencia'])} h"
                if es_num(a["rest"]):
                    txt += f"  ·  restan {fmt_num(a['rest'])}" if a["rest"] > 0 else "  ·  vencido"
            else:
                txt = f"{a['ult']} · cada {fmt_num(a['frecuencia'])} h"
            self.create_text(x_bar + w_bar + 8, cy, text=txt, anchor="w", fill=TEXTO, font=(FUENTE, 8))
            xe = w - w_est
            etiqueta = a["estado"] if a["estado"] != "-" else "Sin registro"
            self.create_rectangle(xe, cy - 10, w - 6, cy + 10, fill=col, outline="")
            self.create_text((xe + w - 6) / 2, cy, text=etiqueta, fill="#FFFFFF", font=(FUENTE, 8, "bold"))
            y += self.ALTO


class FranjaSeguridad(tk.Canvas):
    """Franja diagonal amarilla y negra (señalética de mantenimiento)."""

    def __init__(self, parent, alto=7):
        super().__init__(parent, height=alto, highlightthickness=0, background=AMARILLO)
        self.alto = alto
        self.bind("<Configure>", self._dibujar)

    def _dibujar(self, e):
        self.delete("all")
        h = self.alto
        for x in range(-h, e.width + h, 2 * h + 4):
            self.create_polygon(x, h, x + h, 0, x + 2 * h, 0, x + h, h, fill="#222831", outline="")


class DialogoTexto(tk.Toplevel):
    """InputBox: mensaje multilínea + campo de texto."""

    def __init__(self, parent, msg, titulo, defecto=""):
        super().__init__(parent)
        self.title(titulo or TITULO)
        self.transient(parent)
        self.resizable(False, False)
        self.resultado = None
        ttk.Label(self, text=msg, justify="left", wraplength=520, padding=12).pack(anchor="w")
        self.var = tk.StringVar(value=defecto)
        e = ttk.Entry(self, textvariable=self.var, width=40)
        e.pack(padx=12, pady=(0, 8), anchor="w")
        b = ttk.Frame(self, padding=(12, 0, 12, 12))
        b.pack(fill="x")
        ttk.Button(b, text="Aceptar", command=self._ok).pack(side="right", padx=4)
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        e.focus_set()
        e.select_range(0, "end")
        _centrar(self, parent)
        self.grab_set()
        self.wait_window()

    def _ok(self):
        self.resultado = self.var.get()
        self.destroy()


class DialogoResumen(tk.Toplevel):
    """Turno (obligatorio) y período del resumen de PM."""

    def __init__(self, parent, desde: str, hasta: str):
        super().__init__(parent)
        self.title(f"{TITULO} · Resumen de PM")
        self.transient(parent)
        self.resizable(False, False)
        self.resultado = None
        f = tk.Frame(self, background=TARJETA, padx=22, pady=18)
        f.pack(fill="both")
        self._img = tema.icono(self, "historial", 22, ACENTO)
        tk.Label(f, image=self._img, text="  Resumen de PM ejecutadas", compound="left", background=TARJETA,
                 foreground=NAVY, font=(FUENTE, 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(f, text="¿A qué turno pertenece este resumen?", background=TARJETA, foreground=TEXTO,
                 font=(FUENTE, 10, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(14, 6))
        self.turno = tk.StringVar(value="")
        bt = tk.Frame(f, background=TARJETA)
        bt.grid(row=2, column=0, columnspan=2, sticky="w")
        self._botones = {}
        for t in ("Turno A", "Turno B"):
            b = tk.Label(bt, text=t, width=12, pady=10, cursor="hand2", font=(FUENTE, 11, "bold"),
                         background="#EEF2F6", foreground=NAVY, highlightthickness=2, highlightbackground=BORDE)
            b.pack(side="left", padx=(0, 10))
            b.bind("<Button-1>", lambda _e, t=t: self._elegir(t))
            self._botones[t] = b
        tk.Label(f, text="Período (dd-mm-aaaa)", background=TARJETA, foreground=TEXTO, font=(FUENTE, 10, "bold")
                 ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 6))
        self.v1, self.v2 = tk.StringVar(value=desde), tk.StringVar(value=hasta)
        for i, (lbl, v) in enumerate((("Desde", self.v1), ("Hasta", self.v2))):
            tk.Label(f, text=lbl, background=TARJETA, foreground=SUAVE).grid(row=4 + i, column=0, sticky="w")
            ttk.Entry(f, textvariable=v, width=14).grid(row=4 + i, column=1, sticky="w", pady=2, padx=(8, 0))
        tk.Label(f, text="Por defecto: los últimos 7 días (semana del turno).", background=TARJETA,
                 foreground=SUAVE, font=(FUENTE, 8)).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
        b = tk.Frame(f, background=TARJETA)
        b.grid(row=7, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(b, text="Cancelar", style="Gris.TButton", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Generar PDF", style="Verde.TButton", command=self._ok).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _e: self.destroy())
        _centrar(self, parent)
        self.grab_set()
        self.wait_window()

    def _elegir(self, t):
        self.turno.set(t)
        for k, b in self._botones.items():
            sel = k == t
            b.configure(background=ACENTO if sel else "#EEF2F6", foreground="#FFFFFF" if sel else NAVY,
                        highlightbackground=ACENTO if sel else BORDE)

    def _ok(self):
        from .util import parse_fecha
        if not self.turno.get():
            messagebox.showwarning(TITULO, "Seleccione el turno (Turno A o Turno B).", parent=self)
            return
        d1, d2 = parse_fecha(self.v1.get()), parse_fecha(self.v2.get())
        if d1 is None or d2 is None:
            messagebox.showwarning(TITULO, "Ingrese fechas válidas con formato dd-mm-aaaa.", parent=self)
            return
        if d2 < d1:
            messagebox.showwarning(TITULO, "La fecha «Hasta» debe ser igual o posterior a «Desde».", parent=self)
            return
        self.resultado = dict(turno=self.turno.get(), desde=d1, hasta=d2)
        self.destroy()


class DialogoVarios(tk.Toplevel):
    """Lista de casillas para elegir uno o varios elementos."""

    def __init__(self, parent, msg, opciones):
        super().__init__(parent)
        self.title(TITULO)
        self.transient(parent)
        self.resultado = None
        ttk.Label(self, text=msg, justify="left", wraplength=480, padding=12).pack(anchor="w")
        self.vars = []
        f = ttk.Frame(self, padding=(16, 0))
        f.pack(fill="both")
        for i, o in enumerate(opciones):
            v = tk.BooleanVar()
            ttk.Checkbutton(f, text=f"{i + 1}. {o}", variable=v).pack(anchor="w", pady=1)
            self.vars.append(v)
        b = ttk.Frame(self, padding=12)
        b.pack(fill="x")
        ttk.Button(b, text="Aceptar", command=self._ok).pack(side="right", padx=4)
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        _centrar(self, parent)
        self.grab_set()
        self.wait_window()

    def _ok(self):
        sel = [i for i, v in enumerate(self.vars) if v.get()]
        if not sel:
            messagebox.showwarning(TITULO, "Marque al menos un aceite.", parent=self)
            return
        self.resultado = sel
        self.destroy()


class DialogoFila(tk.Toplevel):
    """Formulario para editar una fila (dict) según una especificación de columnas."""

    def __init__(self, parent, titulo, columnas, fila: dict):
        super().__init__(parent)
        self.title(titulo)
        self.transient(parent)
        self.resultado = None
        self.columnas = columnas
        self.vars = {}
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        for i, (k, tit, tipo, ancho) in enumerate(columnas):
            ttk.Label(f, text=tit).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            v = fila.get(k)
            if tipo == "fecha" and v is not None and hasattr(v, "strftime"):
                v = v.strftime("%d-%m-%Y")
            elif tipo in ("num", "int") and es_num(v):
                v = int(v) if float(v) == int(v) else v
            var = tk.StringVar(value="" if v is None else str(v))
            ttk.Entry(f, textvariable=var, width=max(12, min(ancho // 6, 70))).grid(row=i, column=1, sticky="w", pady=2)
            self.vars[k] = var
        b = ttk.Frame(self, padding=(12, 0, 12, 12))
        b.pack(fill="x")
        ttk.Button(b, text="Aceptar", command=self._ok).pack(side="right", padx=4)
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        _centrar(self, parent)
        self.grab_set()
        self.wait_window()

    def _ok(self):
        from .util import parse_fecha
        out = {}
        for k, tit, tipo, _ in self.columnas:
            s = self.vars[k].get().strip()
            if tipo in ("num", "int"):
                if s == "":
                    out[k] = None
                    continue
                n = parse_num(s)
                if n is None:
                    messagebox.showwarning(TITULO, f"«{tit}» debe ser numérico.", parent=self)
                    return
                out[k] = int(n) if tipo == "int" else n
            elif tipo == "fecha":
                if s == "":
                    out[k] = None
                    continue
                d = parse_fecha(s)
                if d is None:
                    messagebox.showwarning(TITULO, f"«{tit}»: use el formato dd-mm-aaaa.", parent=self)
                    return
                out[k] = d
            else:
                out[k] = s
        self.resultado = out
        self.destroy()


class EditorTabla(tk.Toplevel):
    """Editor genérico de una tabla de configuración (lista de dicts)."""

    def __init__(self, parent, titulo, columnas, filas, al_guardar, nota=""):
        super().__init__(parent)
        self.title(f"{TITULO} · {titulo}")
        self.transient(parent)
        self.geometry("1100x560")
        self.columnas = columnas
        self.filas = [dict(f) for f in filas]
        self.al_guardar = al_guardar
        if nota:
            ttk.Label(self, text=nota, wraplength=1000, foreground="#595959", padding=(10, 8, 10, 0)).pack(anchor="w")
        marco, self.tv = tabla(self, [(k, t, a, "w") for k, t, _, a in columnas], height=18)
        marco.pack(fill="both", expand=True, padx=10, pady=8)
        self.tv.bind("<Double-1>", lambda _e: self.editar())
        b = ttk.Frame(self, padding=(10, 0, 10, 10))
        b.pack(fill="x")
        for txt, cmd in (("Agregar", self.agregar), ("Editar", self.editar), ("Eliminar", self.eliminar),
                         ("Subir", lambda: self.mover(-1)), ("Bajar", lambda: self.mover(1))):
            ttk.Button(b, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(b, text="Guardar", style="Accion.TButton", command=self.guardar).pack(side="right", padx=2)
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=2)
        self.refrescar()
        _centrar(self, parent)
        self.grab_set()

    def refrescar(self, sel=None):
        llenar(self.tv, [[f.get(k) for k, *_ in self.columnas] for f in self.filas])
        hijos = self.tv.get_children()
        if sel is not None and 0 <= sel < len(hijos):
            self.tv.selection_set(hijos[sel])
            self.tv.see(hijos[sel])

    def _sel(self):
        s = self.tv.selection()
        return self.tv.index(s[0]) if s else None

    def agregar(self):
        i = self._sel()
        base = dict(self.filas[i]) if i is not None else {}
        d = DialogoFila(self, "Agregar fila", self.columnas, base)
        if d.resultado is not None:
            pos = len(self.filas) if i is None else i + 1
            self.filas.insert(pos, d.resultado)
            self.refrescar(pos)

    def editar(self):
        i = self._sel()
        if i is None:
            return
        d = DialogoFila(self, "Editar fila", self.columnas, self.filas[i])
        if d.resultado is not None:
            self.filas[i].update(d.resultado)
            self.refrescar(i)

    def eliminar(self):
        i = self._sel()
        if i is not None and messagebox.askyesno(TITULO, "¿Eliminar la fila seleccionada?", parent=self):
            del self.filas[i]
            self.refrescar(min(i, len(self.filas) - 1))

    def mover(self, d):
        i = self._sel()
        if i is None or not 0 <= i + d < len(self.filas):
            return
        self.filas[i], self.filas[i + d] = self.filas[i + d], self.filas[i]
        self.refrescar(i + d)

    def guardar(self):
        self.al_guardar(self.filas)
        self.destroy()


class Desplazable(ttk.Frame):
    """Marco con desplazamiento vertical y horizontal."""

    def __init__(self, parent):
        super().__init__(parent, style="Pagina.TFrame")
        self.canvas = tk.Canvas(self, highlightthickness=0, background=FONDO)
        sy = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        sx = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.interior = ttk.Frame(self.canvas, style="Pagina.TFrame", padding=10)
        self.interior.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=max(e.width, 1080)))
        self.canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._rueda))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _rueda(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


def _centrar(win, parent):
    win.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 3
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
    except tk.TclError:
        pass
