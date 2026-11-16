"""Actualización automática del ejecutable desde las «Releases» de GitHub.

Flujo: consulta la última versión publicada, descarga el nuevo PlanificacionPM.exe junto al actual y
lanza un pequeño script que espera a que el programa se cierre, reemplaza el archivo y lo vuelve a abrir.
Los datos no se tocan: viven en Documentos\\PlanificacionPM."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import __version__

REPO = "RodrigoAvila321/Prueba"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}/releases/latest"
ACTIVO = "PlanificacionPM.exe"


def version_tupla(v: str) -> tuple:
    v = str(v).strip().lstrip("vV")
    partes = []
    for p in v.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        partes.append(int(num) if num else 0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes)


def es_mas_nueva(remota: str, local: str = __version__) -> bool:
    return version_tupla(remota) > version_tupla(local)


def ultima_version(timeout: float = 8.0) -> dict | None:
    """Devuelve {'version', 'url', 'notas', 'tamano'} de la última release, o None si no hay."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "PlanificacionPM-actualizador"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        datos = json.load(r)
    for a in datos.get("assets", []):
        if a.get("name", "").lower() == ACTIVO.lower():
            return {"version": datos.get("tag_name", ""), "url": a["browser_download_url"],
                    "notas": datos.get("body") or "", "tamano": a.get("size", 0)}
    return None


def ejecutable_actual() -> Path | None:
    """Ruta del .exe en uso (solo cuando el programa corre compilado)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


def descargar(url: str, destino: Path, progreso=None, timeout: float = 30.0):
    req = urllib.request.Request(url, headers={"User-Agent": "PlanificacionPM-actualizador"})
    tmp = destino.with_suffix(".descargando")
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        hecho = 0
        while True:
            bloque = r.read(256 * 1024)
            if not bloque:
                break
            f.write(bloque)
            hecho += len(bloque)
            if progreso:
                progreso(hecho, total)
    if total and hecho != total:
        tmp.unlink(missing_ok=True)
        raise OSError("La descarga quedó incompleta. Intente nuevamente.")
    os.replace(tmp, destino)


def script_reemplazo(nuevo: Path, actual: Path) -> str:
    """Script .bat: reintenta el reemplazo hasta que el .exe en uso se libere y luego lo abre."""
    return "\r\n".join([
        "@echo off",
        "set /a n=0",
        ":reintentar",
        f'move /Y "{nuevo}" "{actual}" >nul 2>&1',
        "if not errorlevel 1 goto listo",
        "set /a n+=1",
        "if %n% GEQ 90 goto fallo",
        "ping -n 2 127.0.0.1 >nul",
        "goto reintentar",
        ":listo",
        f'start "" "{actual}"',
        'del "%~f0"',
        "exit /b 0",
        ":fallo",
        f'start "" "{actual}"',
        'del "%~f0"',
        "",
    ])


def instalar_y_reiniciar(nuevo: Path, actual: Path):
    """Lanza el script de reemplazo (proceso independiente). El llamador debe cerrar el programa enseguida."""
    bat = Path(tempfile.gettempdir()) / "PlanificacionPM_actualizar.bat"
    bat.write_text(script_reemplazo(nuevo, actual), encoding="mbcs" if sys.platform.startswith("win") else "utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True)
