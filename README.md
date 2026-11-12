# Planificación PM: programa de escritorio

Migración completa del libro **Planificacion_PM (.xlsm)** a un programa en Python con interfaz gráfica,
distribuible como ejecutable de Windows (`PlanificacionPM.exe`). No necesita Excel ni macros. Excel solo se
usa como formato de salida en las exportaciones.

## Obtener el ejecutable

Cada `push` compila el `.exe` en GitHub Actions (workflow **Compilar ejecutable Windows**):

1. Vaya a la pestaña **Actions** del repositorio, abra la última ejecución correcta.
2. Descargue el artefacto **PlanificacionPM-windows** (zip con `PlanificacionPM.exe`).
3. Copie `PlanificacionPM.exe` a una carpeta propia (por ejemplo `Documentos\PlanificacionPM`).

Para compilarlo en Windows sin GitHub: instale Python 3.12 desde python.org (marque «Add python.exe to PATH»),
haga doble clic en `compilar_windows.bat` y tome el ejecutable de `dist\PlanificacionPM.exe`. Equivale a:

```bash
pip install -r requirements-dev.txt
python -c "from planificacion_pm.tema import guardar_ico; guardar_ico('icono.ico')"
pyinstaller --noconfirm --onefile --windowed --icon icono.ico --name PlanificacionPM main.py
```

Para ejecutarlo sin compilar: `pip install -r requirements.txt` y luego `python main.py`.

## Primer uso

1. Al abrir por primera vez, el programa pide el libro Excel original (`.xlsm`) e importa Historial,
   cambios de aceite, lecturas, programación, configuración, kits, descripciones y los formatos de
   solicitud de análisis (hojas ocultas «Formato DI650i / DR412i»).
   También acepta un respaldo del programa (`.db`) para recuperar todos los datos tal como estaban.
   Más adelante se puede importar o restaurar desde **Configuración > Importar o restaurar datos**.
2. Los datos quedan en `Documentos\PlanificacionPM\PlanificacionPM_datos.db`, así que el `.exe` puede
   estar en el escritorio o en cualquier carpeta. Si junto al `.exe` existe un `PlanificacionPM_datos.db`, se usa
   ese (modo portátil, útil en una carpeta compartida). Respáldelo desde **Configuración > Respaldar base de datos**.
3. Tras la importación se ofrece crear el acceso directo **Planificación PM** en el escritorio (también en
   **Configuración > Crear acceso directo en el escritorio**). Desde ahí se abre como cualquier aplicación.
4. Igual que el `Auto_Open` del libro, cada vez que se abre se pide el horómetro de hoy del equipo seleccionado.

## Correspondencia con el libro original

| Excel (hoja / macro) | Programa |
|---|---|
| Hoja **Panel** + hojas ocultas **Calc** | Pestaña **Panel** (tarjetas, control de aceites, kit, avance de horómetro, últimas PM, proyección 6 meses) |
| `Auto_Open`, `ActualizarHorometro` | Solicitud al abrir y botón **Actualizar horómetro** |
| `DarEjecutada` / `GuardarDatos` | **Dar ejecutada** (mismas validaciones y confirmación aceite por aceite) |
| `ProgramarPM` | **Programar PM** (avisos de riesgo y de exceso de horas; fecha vacía = anular) |
| `EliminarUltimaPM` | **Eliminar última PM** (borra sus aceites y restituye la programación) |
| `LimpiarFormulario` | **Limpiar formulario** |
| `CambioAceiteIndividual` | **Cambio de aceite** (selección con casillas) |
| `ExportarSolicitudAnalisis` | **Solicitud de análisis** (usa el formato del laboratorio importado) |
| Hoja **Historial**, `RepararClaves`, `CorregirFechasFuturas` | Pestaña **Historial** (filtro, edición, exportar a Excel, reparar claves, corregir fechas futuras) |
| Hoja **Aceites**, `RecalcularHorasAceites`, `AgregarHorasAceites` | Pestaña **Aceites** (la columna de horas acumuladas ya viene incluida) |
| Hoja **Proyección** | Pestaña **Proyección** |
| Hoja **Proyección aceites** + **CalcFlota**, `DefinirPeriodo`, `ExportarCompra` | Pestaña **Proyección aceites** (secciones 1 a 5, **Definir período**, **Exportar**) |
| Hoja **Aceites por semanas**, `CalcularSemanas`, `ExportarSemanas` | Pestaña **Aceites por semanas** (**Calcular**, **Exportar**) |
| Hoja **Kits a solicitar** | Pestaña **Kits a solicitar** |
| Hoja **Kits PM**, **Descripciones repuestos**, `ExportarListado` | Pestaña **Kits PM** (**Exportar listado**, edición de kits y descripciones) |
| Hojas **Lecturas** y **Programación** | Pestaña **Lecturas y programación** |
| Hoja **Configuración** | Pestaña **Configuración** (parámetros y tablas editables, respaldo, reimportación) |
| _(nuevo)_ | **Resumen de PM (PDF)**: pregunta Turno A / B y período; PM ejecutadas, cumplimiento en horas y días, aceites y su estado, puntos clave y firmas |
| `InstalarBotones`, `AjustarSemana`, `IrA…` | Ya no se necesitan (los botones y pestañas son parte del programa) |

### Cambios respecto del libro

- Las fechas de **Proyección aceites** y **Aceites por semanas** se escriben en campos de la pestaña
  (antes había cuadros de diálogo y celdas amarillas). Las validaciones son las mismas: desde 01-01-2023,
  como máximo hoy + 60 meses y de 1 a 52 semanas.
- En **Proyección**, la columna de cierre usa el tipo de cierre de cada modelo (PM 1500 en DI650i, PM 2000 en
  DR412i). La hoja original mostraba siempre «PM 1500».
- Las tablas Historial y Aceites se editan con doble clic. Las posiciones de ciclo se recalculan solas.
- El usuario que registra puede fijarse en Configuración. Si no se fija, se usa el usuario de Windows,
  equivalente a `Application.UserName`.

## Verificación

`tests/test_equivalencia.py` importa el libro original y compara el motor de Python con los valores que
Excel dejó calculados: Calc, Panel, control de aceites, las 600 PM proyectadas de CalcFlota, Proyección
aceites, Aceites por semanas y Kits a solicitar.

```bash
PLANPM_XLSM=ruta/Planificacion_PM.xlsm python -m pytest -q tests
```

## Estructura

```
main.py                      punto de entrada
planificacion_pm/
  motor.py                   cálculos (fórmulas de Calc, CalcFlota y hojas de proyección)
  acciones.py                macros (Dar ejecutada, Programar, Eliminar, horómetro, aceites…)
  exportar.py                exportaciones a Excel
  importar.py                importación desde el .xlsm
  db.py                      base de datos SQLite
  app.py, widgets.py         interfaz gráfica (Tkinter)
tests/                       pruebas
```
