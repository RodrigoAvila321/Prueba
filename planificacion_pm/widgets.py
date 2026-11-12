"""Componentes de interfaz reutilizables (Tkinter)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from . import TITULO
from .util import es_num, fmt_num, parse_num

AZUL = "#1F3864"
AZUL_CLARO = "#DDEBF7"
ROJO = "#C00000"
VERDE = "#00703C"
NARANJA = "#C55A11"


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
    tv.tag_configure("total", background=AZUL_CLARO, foreground=AZUL, font=("Segoe UI", 9, "bold"))
    tv.tag_configure("rojo", background="#F8CBAD")
    tv.tag_configure("amarillo", background="#FFF2CC")
    tv.tag_configure("verde", background="#E2EFDA")
    tv.tag_configure("kit", background=AZUL_CLARO)
    tv.tag_configure("gris", foreground="#7F7F7F")
    return marco, tv


def llenar(tv, filas, tags=None):
    tv.delete(*tv.get_children())
    for i, f in enumerate(filas):
        t = tags[i] if tags else ()
        tv.insert("", "end", values=[_txt(v) for v in f], tags=t if isinstance(t, tuple) else (t,))


def _txt(v):
    if v is None:
        return ""
    if es_num(v):
        return fmt_num(v)
    if hasattr(v, "strftime"):
        return v.strftime("%d-%m-%Y")
    return str(v)


class Tarjeta(ttk.Frame):
    """Etiqueta + valor destacado (como las tarjetas del Panel)."""

    def __init__(self, parent, titulo, ancho=18):
        super().__init__(parent, style="Tarjeta.TFrame", padding=(8, 4))
        self.lbl = ttk.Label(self, text=titulo, style="TarjetaTit.TLabel", wraplength=ancho * 8)
        self.lbl.pack(anchor="w")
        self.val = ttk.Label(self, text="", style="TarjetaVal.TLabel", wraplength=ancho * 9)
        self.val.pack(anchor="w")

    def set(self, valor, color=None, titulo=None):
        self.val.configure(text=_txt(valor), foreground=color or AZUL)
        if titulo is not None:
            self.lbl.configure(text=titulo)


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
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#FFFFFF")
        sy = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        sx = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.interior = ttk.Frame(self.canvas, style="Fondo.TFrame", padding=8)
        self.interior.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=max(e.width, self.interior.winfo_reqwidth() if self._ajustar_min else e.width)))
        self._ajustar_min = False
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
