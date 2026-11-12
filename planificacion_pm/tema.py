"""Tema visual «mantenimiento industrial»: paleta, estilos ttk e íconos dibujados con Pillow."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

# ------------------------------------------------------------------ paleta
FONDO = "#EEF2F6"        # fondo de las páginas
TARJETA = "#FFFFFF"      # tarjetas
BORDE = "#D8E0E9"
NAVY = "#15233A"         # barra lateral
NAVY2 = "#22354F"        # encabezados de tabla / ítem activo
NAVY_HOVER = "#1C2D47"
TEXTO = "#1F2A37"
SUAVE = "#6B7785"
ACENTO = "#F28C28"       # naranja seguridad
AMARILLO = "#F6C343"     # amarillo señalética
VERDE = "#2E9E5B"
ROJO = "#D64545"
AZUL = "#1F6FB2"
MORADO = "#7B4FB0"
GRIS = "#6B7785"

FUENTE = "Segoe UI"

_cache: dict = {}


def _aclarar(color: str, f: float = 0.15) -> str:
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * f) for v in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def aplicar(root: tk.Tk):
    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass
    base = (FUENTE, 10)
    root.option_add("*Font", base)
    root.option_add("*Toplevel.background", TARJETA)
    root.configure(background=FONDO)
    s.configure(".", font=base, background=TARJETA, foreground=TEXTO, bordercolor=BORDE,
                lightcolor=BORDE, darkcolor=BORDE, troughcolor="#E6EBF1", focuscolor=ACENTO)
    for est in ("TFrame", "TLabel", "TCheckbutton", "TLabelframe", "TLabelframe.Label"):
        s.configure(est, background=TARJETA, foreground=TEXTO)
    s.configure("Pagina.TFrame", background=FONDO)
    s.configure("Card.TFrame", background=TARJETA, relief="solid", borderwidth=1, bordercolor=BORDE,
                lightcolor=BORDE, darkcolor=BORDE)
    s.configure("Fondo.TFrame", background=FONDO)
    s.configure("Titulo.TLabel", foreground=NAVY, font=(FUENTE, 15, "bold"))
    s.configure("PagTitulo.TLabel", background=FONDO, foreground=NAVY, font=(FUENTE, 15, "bold"))
    s.configure("PagNota.TLabel", background=FONDO, foreground=SUAVE)
    s.configure("Nota.TLabel", foreground=SUAVE)
    s.configure("SecTitulo.TLabel", foreground=NAVY, font=(FUENTE, 11, "bold"))
    s.configure("Alerta.TLabel", foreground=ROJO, font=(FUENTE, 10, "bold"))
    s.configure("Oculto.TNotebook", background=FONDO, borderwidth=0, tabmargins=0)
    s.layout("Oculto.TNotebook.Tab", [])
    s.configure("TNotebook", background=FONDO, borderwidth=0)
    s.configure("TEntry", fieldbackground="#FBFCFE", padding=4)
    s.configure("TCombobox", fieldbackground="#FBFCFE", padding=3, arrowsize=14)
    s.configure("Treeview", rowheight=26, background=TARJETA, fieldbackground=TARJETA, borderwidth=0,
                font=(FUENTE, 9))
    s.map("Treeview", background=[("selected", "#FCE1C6")], foreground=[("selected", TEXTO)])
    s.configure("Treeview.Heading", background=NAVY2, foreground="#FFFFFF", font=(FUENTE, 9, "bold"),
                relief="flat", padding=(4, 6))
    s.map("Treeview.Heading", background=[("active", NAVY)])
    s.configure("Vertical.TScrollbar", arrowsize=12, background="#D5DCE5", bordercolor=FONDO)
    s.configure("Horizontal.TScrollbar", arrowsize=12, background="#D5DCE5", bordercolor=FONDO)
    for nombre, color in (("Verde", VERDE), ("Rojo", ROJO), ("Azul", AZUL), ("Naranja", ACENTO),
                          ("Gris", GRIS), ("Morado", MORADO)):
        s.configure(f"{nombre}.TButton", background=color, foreground="#FFFFFF", font=(FUENTE, 9, "bold"),
                    padding=(14, 7), borderwidth=0, bordercolor=color, lightcolor=color, darkcolor=color,
                    focuscolor=color, relief="flat")
        s.map(f"{nombre}.TButton", background=[("pressed", NAVY), ("active", _aclarar(color, 0.18))],
              bordercolor=[("active", _aclarar(color, 0.18))], lightcolor=[("active", _aclarar(color, 0.18))],
              darkcolor=[("active", _aclarar(color, 0.18))])
    s.configure("Accion.TButton", font=(FUENTE, 9, "bold"))


# ------------------------------------------------------------------ íconos
def _base(n=256):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _engranaje(d, cx, cy, r_ext, r_int, r_hueco, dientes, color):
    pts = []
    for i in range(dientes * 4):
        a = 2 * math.pi * i / (dientes * 4)
        r = r_ext if (i % 4) in (1, 2) else r_int
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=color)
    d.ellipse((cx - r_int + 4, cy - r_int + 4, cx + r_int - 4, cy + r_int - 4), fill=color)
    d.ellipse((cx - r_hueco, cy - r_hueco, cx + r_hueco, cy + r_hueco), fill=(0, 0, 0, 0))


def _llave(d, color, x0=40, y0=216, x1=176, y1=80, ancho=34):
    d.line((x0, y0, x1, y1), fill=color, width=ancho)
    d.ellipse((x0 - ancho / 2, y0 - ancho / 2, x0 + ancho / 2, y0 + ancho / 2), fill=color)
    d.ellipse((x1 - 46, y1 - 46, x1 + 46, y1 + 46), fill=color)
    dx, dy = (x1 - x0), (y1 - y0)
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    bx, by = x1 + ux * 34, y1 + uy * 34
    d.ellipse((bx - 26, by - 26, bx + 26, by + 26), fill=(0, 0, 0, 0))
    d.polygon([(x1 + ux * 10 - uy * 14, y1 + uy * 10 + ux * 14), (x1 + ux * 10 + uy * 14, y1 + uy * 10 - ux * 14),
               (bx + uy * 14, by - ux * 14), (bx - uy * 14, by + ux * 14)], fill=(0, 0, 0, 0))


def dibujar(nombre: str, color="#FFFFFF") -> Image.Image:
    img, d = _base()
    c = color
    T = (0, 0, 0, 0)
    if nombre == "config":
        _engranaje(d, 128, 128, 112, 86, 36, 9, c)
    elif nombre == "herramientas":
        _llave(d, c)
    elif nombre == "logo":
        d.ellipse((0, 0, 255, 255), fill=ACENTO)
        _engranaje(d, 128, 128, 92, 70, 28, 9, "#FFFFFF")
        d.ellipse((100, 100, 156, 156), fill=ACENTO)
        d.ellipse((114, 114, 142, 142), fill="#FFFFFF")
    elif nombre == "aceite":
        d.polygon([(128, 18), (58, 132), (198, 132)], fill=c)
        d.ellipse((56, 92, 200, 236), fill=c)
        d.ellipse((92, 150, 120, 200), fill=T)
    elif nombre == "litros":
        d.rounded_rectangle((56, 30, 200, 226), radius=26, fill=c)
        for y in (88, 168):
            d.rectangle((56, y - 6, 200, y + 6), fill=T)
        d.rectangle((150, 30, 172, 46), fill=T)
    elif nombre == "calendario":
        d.rounded_rectangle((28, 46, 228, 228), radius=24, outline=c, width=20)
        d.rectangle((28, 46, 228, 104), fill=c)
        for x in (80, 176):
            d.rounded_rectangle((x - 10, 20, x + 10, 74), radius=8, fill=c)
        for i in range(3):
            for j in range(2):
                x, y = 74 + i * 54, 140 + j * 46
                d.rectangle((x - 12, y - 12, x + 12, y + 12), fill=c)
    elif nombre == "kit":
        d.rounded_rectangle((34, 92, 222, 226), radius=14, fill=c)
        d.rounded_rectangle((22, 56, 234, 108), radius=12, fill=c)
        d.rectangle((22, 98, 234, 110), fill=T)
        d.rectangle((114, 56, 142, 226), fill=T)
        d.rectangle((96, 30, 160, 44), fill=c)
        d.rectangle((96, 30, 108, 60), fill=c)
        d.rectangle((148, 30, 160, 60), fill=c)
    elif nombre == "proyeccion":
        d.line((36, 28, 36, 222, 228, 222), fill=c, width=20, joint="curve")
        d.line((70, 186, 118, 128, 156, 156, 214, 70), fill=c, width=22, joint="curve")
        d.polygon([(226, 52), (178, 62), (216, 100)], fill=c)
    elif nombre == "historial":
        d.rounded_rectangle((44, 42, 212, 236), radius=20, outline=c, width=20)
        d.rounded_rectangle((88, 20, 168, 66), radius=12, fill=c)
        for y in (104, 146, 188):
            d.ellipse((76, y - 9, 94, y + 9), fill=c)
            d.line((112, y, 182, y), fill=c, width=16)
    elif nombre == "reloj":
        d.ellipse((24, 24, 232, 232), outline=c, width=22)
        d.line((128, 128, 128, 66), fill=c, width=20)
        d.line((128, 128, 174, 156), fill=c, width=20)
        d.ellipse((114, 114, 142, 142), fill=c)
    elif nombre == "panel":
        d.arc((22, 40, 234, 252), 180, 360, fill=c, width=30)
        for a in (200, 240, 300, 340):
            r = math.radians(a)
            d.line((128 + 70 * math.cos(r), 146 + 70 * math.sin(r), 128 + 86 * math.cos(r), 146 + 86 * math.sin(r)),
                   fill=c, width=12)
        d.line((128, 146, 186, 82), fill=c, width=18)
        d.ellipse((104, 122, 152, 170), fill=c)
        d.rounded_rectangle((60, 196, 196, 226), radius=10, fill=c)
    elif nombre == "ayuda":
        d.ellipse((20, 20, 236, 236), fill=c)
        d.ellipse((112, 62, 144, 94), fill=T)
        d.rounded_rectangle((112, 112, 144, 196), radius=10, fill=T)
    elif nombre == "camion":
        d.rounded_rectangle((20, 70, 160, 180), radius=10, fill=c)
        d.polygon([(166, 100), (210, 100), (236, 140), (236, 180), (166, 180)], fill=c)
        for x in (66, 196):
            d.ellipse((x - 30, 162, x + 30, 222), fill=c)
            d.ellipse((x - 12, 180, x + 12, 204), fill=T)
    else:
        d.ellipse((60, 60, 196, 196), fill=c)
    return img


def icono(root, nombre: str, tam: int = 18, color="#FFFFFF") -> ImageTk.PhotoImage:
    clave = (nombre, tam, color)
    if clave not in _cache:
        img = dibujar(nombre, color).resize((tam, tam), Image.LANCZOS)
        _cache[clave] = ImageTk.PhotoImage(img, master=root)
    return _cache[clave]


def guardar_ico(ruta: str):
    img = dibujar("logo")
    img.save(ruta, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
