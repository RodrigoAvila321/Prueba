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


def test_restaurar_respaldo(tmp_path):
    import sqlite3
    import pytest
    origen = _repo(tmp_path)
    origen.agregar_historial({"id": 1, "equipo": "X1", "modelo": "M", "tipo": 250, "fecha": dt.date(2026, 1, 1),
                              "horo": 250})
    origen.cx.commit()
    resp = tmp_path / "respaldo.db"
    dst = sqlite3.connect(resp)
    origen.cx.backup(dst)
    dst.close()
    nuevo = Repositorio(tmp_path / "nuevo.db")
    r = nuevo.restaurar_desde(resp)
    assert r["historial"] == 1 and nuevo.get_config("equipos")[0]["equipo"] == "X1"
    malo = tmp_path / "malo.db"
    malo.write_bytes(b"no es una base")
    with pytest.raises(ValueError):
        nuevo.restaurar_desde(malo)
    otro = sqlite3.connect(tmp_path / "otro.db")
    otro.execute("CREATE TABLE x(a)")
    otro.close()
    with pytest.raises(ValueError):
        nuevo.restaurar_desde(tmp_path / "otro.db")
    assert len(nuevo.historial()) == 1


def test_versiones_y_script():
    from pathlib import Path

    from planificacion_pm import actualizar
    assert actualizar.es_mas_nueva("v10.3", "10.2")
    assert actualizar.es_mas_nueva("v11", "10.9.9")
    assert not actualizar.es_mas_nueva("v10.2", "10.2")
    assert not actualizar.es_mas_nueva("v10.1", "10.2")
    bat = actualizar.script_reemplazo(Path("C:/a/nuevo.exe"), Path("C:/a/PlanificacionPM.exe"))
    assert "move /Y" in bat and 'start ""' in bat and "\r\n" in bat


def test_precios_y_necesidad_neta(tmp_path):
    r = _repo(tmp_path)
    r.set_config("diario", [{"equipo": "X1", "parte": "P9", "lubricante": "Diario", "litros_dia": 20}])
    r.set_config("precios", [{"parte": "P9", "lubricante": "Diario", "precio": 1000}])
    hoy = dt.date(2026, 1, 15)
    m = Motor(r, hoy=hoy)
    s = m.semanas(dt.date(2026, 1, 15), 1)          # 7 días x 20 L = 140 L + 20 % = 168 L -> 1 tarro
    f = [x for x in s["filas"] if x["parte"] == "P9"][0]
    assert f["tarros"] == 1 and f["valor"] == 1000
    sin = m.necesidad_neta(s, None, None)
    assert sin["total_tarros"] == 1 and not sin["hay"]
    # Antes se pidió para 08-01 al 21-01: 14 x 20 = 280 + 20 % = 336 L -> 2 tarros (416 L).
    # Consumo 08-01 al 14-01 = 140 L -> saldo 276 L >= 168 L -> no hay que pedir.
    nn = m.necesidad_neta(s, dt.date(2026, 1, 8), dt.date(2026, 1, 21))
    g = [x for x in nn["filas"] if x["parte"] == "P9"][0]
    assert (g["tarros_ant"], g["consumo"], g["saldo"], g["tarros"], g["ahorro"]) == (2, 140, 276, 0, 1)
    assert nn["solape"] == 7 and nn["total_valor"] == 0


def test_entorno_limpio_para_reiniciar():
    from planificacion_pm import actualizar
    env = actualizar.entorno_limpio({"PATH": "x", "_PYI_APPLICATION_HOME_DIR": "C:/t/_MEI1",
                                     "_PYI_PARENT_PROCESS_LEVEL": "1", "_MEIPASS2": "C:/t/_MEI1"})
    assert env == {"PATH": "x", "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    from pathlib import Path
    bat = actualizar.script_reemplazo(Path("C:/a/n.exe"), Path("C:/a/p.exe"))
    assert "set PYINSTALLER_RESET_ENVIRONMENT=1" in bat and "set _PYI_APPLICATION_HOME_DIR=" in bat
    assert 'start "" "%SystemRoot%\\explorer.exe" "C:\\a\\p.exe"' in bat.replace("/", "\\")


def test_inventario_manual_y_reporte_horas(tmp_path):
    r = _repo(tmp_path)
    r.set_config("diario", [{"equipo": "X1", "parte": "P9", "lubricante": "Diario", "litros_dia": 20}])
    hoy = dt.date(2026, 1, 15)
    m = Motor(r, hoy=hoy)
    s = m.semanas(hoy, 2)                       # 14 x 20 = 280 L + 20 % = 336 L -> 2 tarros
    assert not m.inventario_activo()
    r.set_config("inventario", {"P9": {"stock": 50.0, "solicitado": None, "transito": 1.0}})
    m.recargar()
    nn = m.necesidad_neta(s, None, None)
    g = [x for x in nn["filas"] if x["parte"] == "P9"][0]
    assert nn["modo"] == "inventario" and g["disponible"] == 258 and g["tarros"] == 1   # 336 - 258 = 78 L
    # Reporte de horas: equipo con 4 PM y lectura
    for i, (t, h, d) in enumerate([(250, 250, 1), (500, 500, 5), (250, 750, 9), (1000, 1000, 13)]):
        r.agregar_historial({"id": i + 1, "equipo": "X1", "modelo": "M", "tipo": t, "fecha": dt.date(2026, 1, d),
                             "horo": h, "pos": {500: 1, 1000: 2}.get(t)})
    r.set_lectura("X1", 1180, hoy, "u")
    m.recargar()
    f = m.horas_pm(["X1"])[0]
    assert f["faltan"] == 70 and f["objetivo"] == 1250 and not f["programada"]
    from planificacion_pm.reporte_horas import exportar_horas_pdf
    exportar_horas_pdf(m, ["X1"], str(tmp_path / "h.pdf"), "u")
    assert (tmp_path / "h.pdf").stat().st_size > 2000


def test_exportar_pedido(tmp_path):
    import openpyxl

    from planificacion_pm.exportar import exportar_pedido
    r = _repo(tmp_path)
    r.set_config("diario", [{"equipo": "X1", "parte": "P9", "lubricante": "Diario", "litros_dia": 20}])
    r.set_config("precios", [{"parte": "P9", "lubricante": "Diario", "precio": 1000}])
    r.set_config("inventario", {"P9": {"stock": 100.0, "solicitado": None, "transito": None}})
    m = Motor(r, hoy=dt.date(2026, 1, 15))
    exportar_pedido(m, dt.date(2026, 1, 15), 1, str(tmp_path / "p.xlsx"), "u")
    wb = openpyxl.load_workbook(tmp_path / "p.xlsx")
    assert wb.sheetnames == ["Pedido"]
    ws = wb["Pedido"]
    fila = [c.value for c in ws[7] if c.value is not None]
    assert "P9" in [c.value for row in ws.iter_rows(min_row=7) for c in row]
    assert str(ws["A1"].value).startswith("PEDIDO DE ACEITES") and fila
