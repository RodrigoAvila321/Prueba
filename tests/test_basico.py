"""Pruebas que no requieren el libro original."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planificacion_pm.acciones import Acciones  # noqa: E402
from planificacion_pm.db import Repositorio  # noqa: E402
from planificacion_pm.motor import Motor  # noqa: E402
from planificacion_pm.util import fmt_num, parse_fecha, parse_num, redondear, redondear_arriba  # noqa: E402


def test_redondeo_excel():
    assert redondear(2.5) == 3 and redondear(-2.5) == -3 and redondear(0.125, 2) == 0.13
    assert redondear_arriba(2.01) == 3 and redondear_arriba(2.0) == 2 and redondear_arriba(0) == 0


def test_parseo():
    assert parse_fecha("01-11-2026") == dt.date(2026, 11, 1)
    assert parse_fecha("1/11/26") == dt.date(2026, 11, 1)
    assert parse_fecha("31-02-2026") is None
    assert parse_num("10.803") == 10.803 and parse_num("1.234,5") == 1234.5 and parse_num("abc") is None
    assert fmt_num(15073) == "15.073"


def test_posicion_ciclo():
    assert Acciones.posicion_ciclo(1500, 2, 3, "1500,3000,5000") == 3
    assert Acciones.posicion_ciclo(500, 3, 3, "1500") == 1
    assert Acciones.posicion_ciclo(1000, 1, 4, "2000") == 2


def _repo(tmp_path):
    r = Repositorio(tmp_path / "t.db")
    r.set_config("equipos", [{"equipo": "X1", "modelo": "M", "faena": "F"}])
    r.set_config("ciclos", [{"modelo": "M", "pos1": 500, "pos2": 1000, "pos3": 1500, "pos4": None, "largo": 3,
                             "cierres": "1500"}])
    r.set_config("tipos", [{"modelo": "M", "tipos": "250,500,1000,1500"}])
    r.set_config("aceites_cfg", [{"modelo": "M", "componente": "Motor", "frecuencia": 250, "texto": ""}])
    r.set_config("consumo_tipos", [250, 500, 1000, 1500])
    r.set_config("consumo", [{"modelo": "M", "sistema": "Motor", "lubricante": "L1", "parte": "P1", "litros": 50,
                              "250": 1, "500": 1, "1000": 1, "1500": 1}])
    r.set_config("diario", [])
    return r


def test_ciclo_y_proyeccion(tmp_path):
    r = _repo(tmp_path)
    hoy = dt.date(2026, 1, 31)
    for i, (t, h, d) in enumerate([(250, 250, 1), (500, 500, 11), (250, 750, 21), (1000, 1000, 31)]):
        r.agregar_historial({"id": i + 1, "equipo": "X1", "modelo": "M", "faena": "F", "tipo": t,
                             "fecha": dt.date(2026, 1, d), "horo": h, "pos": {500: 1, 1000: 2}.get(t)})
    r.set_lectura("X1", 1100, hoy, "u")
    m = Motor(r, hoy=hoy)
    e = m.estado("X1")
    assert e["sugerido"] == 250 and e["posterior"] == 1500 and e["proyectado"] == 1250
    assert e["promedio"] == 13  # menos de 6 PM: horas/día por defecto
    tipos = [x["tipo"] for x in m.proyeccion("X1", 6)]
    assert tipos == [250, 1500, 250, 500, 250, 1000]
    assert m.proyeccion("X1", 1)[0]["litros"]["P1"] == 50


def test_resumen_pdf(tmp_path):
    from planificacion_pm.resumen_pdf import datos_resumen, exportar_resumen_pdf
    r = _repo(tmp_path)
    hoy = dt.date(2026, 1, 31)
    for i, (t, h, d) in enumerate([(250, 250, 1), (500, 520, 11), (250, 740, 21)]):
        r.agregar_historial({"id": i + 1, "equipo": "X1", "modelo": "M", "faena": "F", "tipo": t,
                             "fecha": dt.date(2026, 1, d), "horo": h, "pos": {500: 1}.get(t)})
        r.agregar_aceite({"id_pm": i + 1, "equipo": "X1", "comp": "Motor", "horo": h, "origen": "En PM",
                          "horas_ac": 270.0 if i == 1 else 220.0})
    m = Motor(r, hoy=hoy)
    res = datos_resumen(m, dt.date(2026, 1, 10), hoy)
    assert [p["est_h"] for p in res["pms"]] == ["Atrasada 20 h", "Adelantada 30 h"]
    assert [a["estado"] for p in res["pms"] for a in p["aceites"]] == ["Atrasado 20 h", "Adelantado 30 h"]
    exportar_resumen_pdf(m, dt.date(2026, 1, 10), hoy, "Turno A", str(tmp_path / "r.pdf"), "u")
    assert (tmp_path / "r.pdf").stat().st_size > 2000
