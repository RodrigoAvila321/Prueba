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
    """Script .bat: reintenta el reemplazo hasta que el .exe en uso se libere y luego lo abre.

    El programa nuevo se abre a través del Explorador de Windows (como un doble clic del usuario): así es
    hijo del escritorio y no hereda nada del proceso que se cerró (variables _PYI_*, carpeta _MEI, ruta de DLL)."""
    return "\r\n".join([
        "@echo off",
        "set PYINSTALLER_RESET_ENVIRONMENT=1",
        "set _PYI_APPLICATION_HOME_DIR=",
        "set _PYI_ARCHIVE_FILE=",
        "set _PYI_PARENT_PROCESS_LEVEL=",
        "set _PYI_SPLASH_IPC=",
        "set _MEIPASS2=",
        "set /a n=0",
        ":reintentar",
        f'move /Y "{nuevo}" "{actual}" >nul 2>&1',
        "if not errorlevel 1 goto listo",
        "set /a n+=1",
        "if %n% GEQ 90 goto fallo",
        "ping -n 2 127.0.0.1 >nul",
        "goto reintentar",
        ":listo",
        "ping -n 2 127.0.0.1 >nul",
        f'start "" "%SystemRoot%\\explorer.exe" "{actual}"',
        'del "%~f0"',
        "exit /b 0",
        ":fallo",
        "ping -n 2 127.0.0.1 >nul",
        f'start "" "%SystemRoot%\\explorer.exe" "{actual}"',
        'del "%~f0"',
        "",
    ])


def entorno_limpio(base: dict | None = None) -> dict:
    """Variables de entorno para abrir otro .exe de PyInstaller sin heredar las de este proceso.

    Si el programa nuevo hereda las variables internas de PyInstaller (_PYI_*, _MEIPASS2), cree ser un
    subproceso del actual y busca python3xx.dll en la carpeta temporal _MEIxxxx de este, que se borra al
    cerrarse -> «Failed to load Python DLL». PYINSTALLER_RESET_ENVIRONMENT=1 hace que arranque limpio."""
    env = dict(os.environ if base is None else base)
    for k in list(env):
        if k.upper().startswith("_PYI_") or k.upper() in ("_MEIPASS2", "_PYIBOOT_SPLASH"):
            del env[k]
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def instalar_y_reiniciar(nuevo: Path, actual: Path):
    """Lanza el script de reemplazo (proceso independiente). El llamador debe cerrar el programa enseguida."""
    bat = Path(tempfile.gettempdir()) / "PlanificacionPM_actualizar.bat"
    bat.write_text(script_reemplazo(nuevo, actual), encoding="mbcs" if sys.platform.startswith("win") else "utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if sys.platform.startswith("win"):
        try:  # PyInstaller fija la ruta de DLL en su carpeta _MEI; no debe heredarla el proceso nuevo
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass
    subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True, env=entorno_limpio())
