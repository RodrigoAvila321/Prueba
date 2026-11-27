"""Pantalla de carga: «Programación PM perforadoras · Por Rodrigo Avila» con una perforadora animada.

Los cuadros se dibujan con Pillow; el cuadro inicial también se guarda como PNG para la pantalla de
inicio inmediata de PyInstaller (se muestra mientras el .exe se descomprime)."""
from __future__ import annotations

import math
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

W, H = 720, 440
TITULO = "Programación PM perforadoras"
SUBTITULO = "Por Rodrigo Avila"

NAVY = (21, 35, 58)
NAVY2 = (34, 53, 79)
NARANJA = (242, 140, 40)
AMARILLO = (246, 195, 67)
BLANCO = (255, 255, 255)
SUAVE = (185, 198, 216)
SUELO = ((122, 84, 52), (101, 70, 44), (86, 60, 39), (70, 50, 34))
SUELO_Y = 312
MASTIL_X = 444
CICLO = 4.2     # segundos de un ciclo de perforación (bajar y subir)


def _fuente(negrita: bool, tam: int):
    nombres = (["segoeuib.ttf", "arialbd.ttf", "Arial Bold.ttf", "Inter-Bold.otf", "DejaVuSans-Bold.ttf"] if negrita
               else ["segoeui.ttf", "arial.ttf", "Arial.ttf", "Inter-Medium.otf", "DejaVuSans.ttf"])
    rutas = ["", "/System/Library/Fonts/Supplemental/", "/Library/Fonts/", "/usr/share/fonts/opentype/inter/",
             "/usr/share/fonts/truetype/dejavu/"]
    for n in nombres:
        for r in rutas:
            try:
                return ImageFont.truetype(r + n, tam)
            except OSError:
                continue
    try:
        return ImageFont.load_default(tam)
    except TypeError:  # Pillow antiguo
        return ImageFont.load_default()


def _centrado(d, y, txt, f, color):
    w = d.textlength(txt, font=f)
    d.text(((W - w) / 2, y), txt, font=f, fill=color)


_FONDO = None


def _fondo() -> Image.Image:
    """Fondo fijo: degradado, textos, cielo, capas de suelo y franja de seguridad."""
    global _FONDO
    if _FONDO is not None:
        return _FONDO
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line((0, y, W, y), fill=(int(14 + 12 * k), int(24 + 16 * k), int(42 + 22 * k)))
    _centrado(d, 30, TITULO, _fuente(True, 34), BLANCO)
    _centrado(d, 80, SUBTITULO, _fuente(False, 18), NARANJA)
    d.line((W / 2 - 60, 112, W / 2 + 60, 112), fill=NARANJA, width=2)
    # suelo por capas
    capas = [SUELO_Y, SUELO_Y + 22, SUELO_Y + 44, SUELO_Y + 66, 404]
    for i in range(4):
        d.rectangle((40, capas[i], W - 40, capas[i + 1]), fill=SUELO[i])
    rng = __import__("random").Random(3)
    for _ in range(260):
        x, y = rng.randint(42, W - 42), rng.randint(SUELO_Y + 4, 402)
        r = rng.choice((1, 1, 2, 3))
        c = tuple(min(255, v + rng.randint(-18, 26)) for v in SUELO[min(3, (y - SUELO_Y) // 22)])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    d.line((40, SUELO_Y, W - 40, SUELO_Y), fill=(160, 118, 76), width=3)
    # franja de seguridad
    d.rectangle((0, H - 12, W, H), fill=AMARILLO)
    for x in range(-12, W + 12, 28):
        d.polygon([(x, H), (x + 12, H - 12), (x + 24, H - 12), (x + 12, H)], fill=(34, 40, 49))
    _FONDO = im
    return im


def _fase(t: float):
    """Profundidad del pozo (0..1) y posición del cabezal según el ciclo bajar / subir."""
    c = (t % CICLO) / CICLO
    if c < 0.75:                       # perforando
        prof = c / 0.75
        subiendo = False
    else:                              # retirando la barra
        prof = 1 - (c - 0.75) / 0.25
        subiendo = True
    return prof, subiendo


def cuadro(t: float, estado: str = "Cargando…") -> Image.Image:
    im = _fondo().copy()
    d = ImageDraw.Draw(im)
    prof, subiendo = _fase(t)
    pozo_max = 78
    fondo_pozo = SUELO_Y + 6 + pozo_max * prof
    # pozo
    d.rectangle((MASTIL_X - 8, SUELO_Y, MASTIL_X + 8, fondo_pozo + 4), fill=(32, 22, 14))
    # orugas
    ox0, ox1, oy = 236, 400, SUELO_Y - 4
    d.rounded_rectangle((ox0, oy - 26, ox1, oy), 13, fill=(44, 48, 56))
    for i in range(7):
        cx = ox0 + 16 + i * 22
        d.ellipse((cx - 8, oy - 21, cx + 8, oy - 5), fill=(92, 98, 108))
        d.ellipse((cx - 3, oy - 16, cx + 3, oy - 10), fill=(44, 48, 56))
    for i in range(14):
        x = ox0 + 8 + i * 11.5
        d.line((x, oy - 26, x, oy - 22), fill=(120, 126, 136), width=2)
    # cuerpo y cabina
    d.rounded_rectangle((246, oy - 70, 392, oy - 26), 6, fill=AMARILLO)
    d.rectangle((246, oy - 40, 392, oy - 34), fill=(34, 40, 49))
    d.rounded_rectangle((256, oy - 104, 312, oy - 70), 6, fill=AMARILLO)
    d.rounded_rectangle((264, oy - 97, 304, oy - 76), 4, fill=(120, 190, 230))
    d.line((268, oy - 92, 280, oy - 80), fill=(190, 230, 250), width=2)
    d.rectangle((328, oy - 86, 338, oy - 70), fill=(60, 64, 72))       # escape
    humo = (t * 1.6) % 1
    for k in range(3):
        f = (humo + k / 3) % 1
        r = 4 + 8 * f
        a = int(140 * (1 - f))
        d.ellipse((333 - r - 10 * f, oy - 92 - 34 * f - r, 333 + r - 10 * f, oy - 92 - 34 * f + r),
                  fill=(150 + a // 3, 150 + a // 3, 160 + a // 3))
    # mástil (torre reticulada)
    top, base = 128, SUELO_Y - 10
    # brazo que une el cuerpo con el mástil y pie apoyado en el suelo
    d.rectangle((388, oy - 66, MASTIL_X - 10, oy - 50), fill=(60, 64, 72))
    d.rectangle((MASTIL_X - 16, base, MASTIL_X + 16, SUELO_Y), fill=(60, 64, 72))
    for xr in (MASTIL_X - 12, MASTIL_X + 12):
        d.line((xr, top, xr, base), fill=NARANJA, width=5)
    for y in range(top + 4, base, 16):
        d.line((MASTIL_X - 12, y, MASTIL_X + 12, y + 16), fill=NARANJA, width=2)
        d.line((MASTIL_X + 12, y, MASTIL_X - 12, y + 16), fill=NARANJA, width=2)
    d.rectangle((MASTIL_X - 18, top - 8, MASTIL_X + 18, top + 2), fill=NARANJA)
    d.line((312, oy - 72, MASTIL_X - 12, top + 60), fill=(60, 64, 72), width=6)  # pistón de soporte
    # cabezal de rotación: baja con la profundidad
    cab_y = top + 18 + (base - top - 60) * prof
    # barra de perforación desde el cabezal hasta el fondo del pozo
    barra_x0, barra_x1 = MASTIL_X - 4, MASTIL_X + 4
    d.rectangle((barra_x0, cab_y + 20, barra_x1, fondo_pozo), fill=(170, 176, 186))
    giro = 0 if subiendo else (t * 90) % 12
    y = cab_y + 20 - 12 + giro
    while y < fondo_pozo:
        d.line((barra_x0, y, barra_x1, y + 6), fill=(110, 116, 126), width=2)
        y += 12
    # broca con dientes
    bx, by = MASTIL_X, fondo_pozo
    d.polygon([(bx - 9, by - 6), (bx + 9, by - 6), (bx + 6, by + 4), (bx - 6, by + 4)], fill=(90, 94, 104))
    for k in range(3):
        ang = (t * 12 + k * 2.09) if not subiendo else k * 2.09
        dx = 6 * math.cos(ang)
        d.ellipse((bx + dx - 2, by + 2, bx + dx + 2, by + 6), fill=(200, 205, 212))
    d.rounded_rectangle((MASTIL_X - 16, cab_y, MASTIL_X + 16, cab_y + 22), 4, fill=(60, 64, 72))
    d.rectangle((MASTIL_X - 10, cab_y + 6, MASTIL_X + 10, cab_y + 12), fill=NARANJA)
    # partículas expulsadas por la boca del pozo
    if not subiendo and prof > 0.03:
        for i in range(14):
            fase = (t * 1.7 + i / 14) % 1
            lado = -1 if i % 2 else 1
            vx = lado * (25 + (i * 37) % 40)
            vy = 55 + (i * 23) % 35
            x = MASTIL_X + vx * fase
            yy = SUELO_Y - vy * fase + 140 * fase * fase
            if yy <= SUELO_Y + 2:
                r = 1.5 + (i % 3)
                c = SUELO[i % 4]
                d.ellipse((x - r, yy - r, x + r, yy + r), fill=tuple(min(255, v + 40) for v in c))
        for i in range(5):  # polvo
            f = (t * 0.9 + i / 5) % 1
            r = 6 + 14 * f
            x = MASTIL_X + (i - 2) * 14 * f
            yy = SUELO_Y - 8 - 22 * f
            g = int(150 - 60 * f)
            d.ellipse((x - r, yy - r, x + r, yy + r), outline=(g, g - 20, g - 40), width=2)
    # estado y puntos de carga
    f = _fuente(False, 14)
    puntos = "." * (1 + int(t * 3) % 3)
    txt = estado.rstrip(".…") + puntos
    w = d.textlength(estado.rstrip(".…") + "...", font=f)
    d.text(((W - w) / 2, 410), txt, font=f, fill=SUAVE)
    return im


def guardar_png(ruta: str):
    """Imagen fija para la pantalla de inicio de PyInstaller (--splash)."""
    cuadro(1.2, "Iniciando").save(ruta)


class PantallaCarga:
    """Ventana sin bordes, centrada, con la animación; se actualiza con `after` o con `paso()`."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.configure(background="#15233A")
        try:
            self.top.attributes("-topmost", True)
        except tk.TclError:
            pass
        sw, sh = self.top.winfo_screenwidth(), self.top.winfo_screenheight()
        self.top.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        self.lbl = tk.Label(self.top, borderwidth=0, background="#15233A")
        self.lbl.pack()
        self.t0 = time.monotonic()
        self.estado = "Cargando datos"
        self.vivo = True
        self.paso()
        self.top.update()
        try:  # cierra la imagen fija de PyInstaller, si existe
            import pyi_splash  # type: ignore
            pyi_splash.close()
        except Exception:
            pass
        self._animar()

    def paso(self):
        if not self.vivo:
            return
        self._img = ImageTk.PhotoImage(cuadro(time.monotonic() - self.t0, self.estado), master=self.top)
        self.lbl.configure(image=self._img)
        self.lbl.update_idletasks()

    def _animar(self):
        if self.vivo:
            self.paso()
            self.root.after(40, self._animar)

    def set_estado(self, txt: str):
        self.estado = txt
        self.paso()

    def esperar(self, segundos: float):
        """Mantiene la animación corriendo durante `segundos` sin bloquear la interfaz."""
        v = tk.BooleanVar(master=self.root)
        self.root.after(int(segundos * 1000), lambda: v.set(True))
        self.root.wait_variable(v)

    def transcurrido(self) -> float:
        return time.monotonic() - self.t0

    def cerrar(self):
        self.vivo = False
        try:
            self.top.destroy()
        except tk.TclError:
            pass
