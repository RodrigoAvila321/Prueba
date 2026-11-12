"""Utilidades: redondeo al estilo Excel, fechas y formatos."""
from __future__ import annotations

import datetime as dt
import math
from decimal import ROUND_HALF_UP, Decimal

ORIGEN_PM = "En PM"
ORIGEN_FUERA = "Fuera de PM"
ORIGEN_NO = "No cambiado"
ORIGEN_IND = "Cambio individual"
SIN_ANTERIOR = "Sin cambio anterior"


def redondear(x: float, n: int = 0) -> float:
    """ROUND de Excel (mitad alejándose de cero)."""
    q = Decimal(1).scaleb(-n)
    return float(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def redondear_arriba(x: float) -> int:
    """ROUNDUP(x, 0) de Excel."""
    r = math.ceil(abs(x) - 1e-12)
    return int(r if x >= 0 else -r)


def es_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def a_fecha(v) -> dt.date | None:
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str):
        try:
            return dt.date.fromisoformat(v[:10])
        except ValueError:
            return parse_fecha(v)
    return None


def a_fechahora(v) -> dt.datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    try:
        return dt.datetime.fromisoformat(str(v))
    except ValueError:
        return None


def parse_fecha(s: str) -> dt.date | None:
    """Convierte dd-mm-aaaa (también / o .) en fecha, como ConvertirFecha de VBA."""
    s = str(s).strip().replace("/", "-").replace(".", "-")
    p = s.split("-")
    if len(p) != 3:
        return None
    try:
        dd, mm, aa = int(p[0]), int(p[1]), int(p[2])
    except ValueError:
        return None
    if aa < 100:
        aa += 2000
    if not (1 <= mm <= 12 and 1 <= dd <= 31 and 2000 <= aa <= 2100):
        return None
    try:
        return dt.date(aa, mm, dd)
    except ValueError:
        return None


def parse_num(s) -> float | None:
    if es_num(s):
        return float(s)
    s = str(s).strip().replace(" ", "")
    if not s:
        return None
    # Acepta 1.234,5 / 1,234.5 / 1234,5 / 1234.5
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fmt_fecha(d) -> str:
    d = a_fecha(d)
    return d.strftime("%d-%m-%Y") if d else ""


def fmt_fechahora(d) -> str:
    d = a_fechahora(d)
    return d.strftime("%d-%m-%Y %H:%M") if d else ""


def fmt_num(x, dec: int = 0) -> str:
    """Formato #,##0 (separador de miles con punto, como Excel en español)."""
    if not es_num(x):
        return "" if x is None else str(x)
    s = f"{redondear(float(x), dec):,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_pct(x) -> str:
    return f"{redondear(float(x) * 100):.0f}%"


def fmt_tipo(t) -> str:
    if es_num(t) and float(t) == int(t):
        return str(int(t))
    return str(t)


def semana_iso(d: dt.date) -> int:
    return d.isocalendar()[1]


def primer_dia_mes(d: dt.date, sumar_meses: int = 0) -> dt.date:
    m = d.month - 1 + sumar_meses
    return dt.date(d.year + m // 12, m % 12 + 1, 1)


def ultimo_dia_mes(d: dt.date) -> dt.date:
    return primer_dia_mes(d, 1) - dt.timedelta(days=1)


def sumar_meses(d: dt.date, n: int) -> dt.date:
    """DateAdd("m", n, d) de VBA (ajusta al último día del mes)."""
    p = primer_dia_mes(d, n)
    return min(dt.date(p.year, p.month, 1) + dt.timedelta(days=d.day - 1), ultimo_dia_mes(p))


def mismo_texto(a, b) -> bool:
    """Comparación de texto como Excel (sin distinguir mayúsculas)."""
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def num_o_cero(v) -> float:
    return float(v) if es_num(v) else 0.0
