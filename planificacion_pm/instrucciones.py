"""Texto de la pestaña Instrucciones (adaptado de la hoja «Instrucciones» del libro original)."""

TEXTO = """
# A. Inicio
1. Al abrir el programa por primera vez, se pide el libro Excel original (.xlsm) o un respaldo (.db) para importar Historial, cambios de aceite, lecturas, programación, configuración, kits y formatos de solicitud de análisis.
2. Los datos quedan en Documentos\\PlanificacionPM\\PlanificacionPM_datos.db (o junto al ejecutable, si ahí ya existe ese archivo). Respáldelo periódicamente (Configuración > Respaldar base de datos).
3. El programa es independiente de Excel: ábralo con el acceso directo «Planificación PM» del escritorio (Configuración > Crear acceso directo en el escritorio).
4. Cada vez que se abre, el programa solicita el horómetro de hoy del equipo seleccionado, mostrando la última PM y la última lectura como referencia. Si se cancela, el Panel muestra una alerta roja «Horómetro no actualizado hoy».
5. Al cambiar de equipo, el Panel muestra la última lectura de ese equipo. Para actualizarla use «Actualizar horómetro». Las lecturas quedan en la pestaña «Lecturas y programación».

# B. Equipos y modelos
1. D10 y D11 son DI650i: ciclo 250 → 500 → 250 → 1000 → 250 → 1500, con 7 aceites.
2. D14, D15 y D16 son DR412i: ciclo 250 → 500 → 250 → 1000 → 250 → 500 → 250 → 2000, con 13 aceites.
3. El modelo de cada equipo, su ciclo, sus tipos de PM válidos y sus aceites se definen en «Configuración». El Panel se adapta al equipo seleccionado.

# C. Panel
1. PM ACTUAL: PM pendiente según el ciclo del modelo, horómetro objetivo, estado de programación, fechas, cumplimiento de la última PM y «Programar PM».
2. ESTADO DE MANTENCIÓN: última PM, horas acumuladas y restantes, estado de la PM actual, promedio real y la próxima PM posterior a la actual.
3. CONTROL DE ACEITES: los aceites del modelo del equipo, con horas desde su último cambio real, estado y frecuencia de cambio. Botones «Cambio de aceite» y «Solicitud de análisis».
4. KIT DE MANTENIMIENTO: kit de la PM actual (N° de kit, ubicación, contenido y repuestos asociados). DR412i PM 500 muestra los dos kits (D14 y D15 - D16).
5. AVANCE DE HORÓMETRO PROYECTADO: avance diario, semanal (× 7) y mensual (× 30), real y con el avance extra; horómetro estimado hoy y a la fecha programada o sugerida (en rojo si supera el objetivo).
6. Franja inferior: datos de la PM a dar por ejecutada, últimas 6 PM y resumen de la proyección a 6 meses.

# D. Registro de PM
1. «Dar ejecutada» registra la PM del equipo seleccionado con los datos del formulario.
2. Se confirma aceite por aceite (según el modelo) si se cambió en la PM; si no, se ingresa el horómetro real del cambio o se deja vacío si aún no se ha cambiado.
3. «Eliminar última PM» borra el último registro del equipo y sus cambios de aceite, y restituye su programación.
4. «Programar PM» asigna la fecha de la PM actual; si es posterior a la sugerida o a la proyectada, advierte el riesgo y el exceso de horas estimado. Con la fecha vacía, anula la programación.
5. «Cambio de aceite» registra el cambio de uno o varios aceites fuera de una PM (Origen «Cambio individual») y reinicia su contador.
7. «Reporte horas a PM (PDF)» (Panel y Lecturas y programación): elija los equipos y obtenga, para cada uno, la PM programada, el horómetro de hoy, el objetivo y las horas que faltan para completar las 250 h, con barra de avance y estado.
6. «Solicitud de análisis» exporta el formato del laboratorio del modelo con la última PM ejecutada del equipo.

# E. Lógica de cálculo
1. Horómetro objetivo = última PM + 250 h. Entre cada PM mayor del ciclo se ejecuta una PM 250; el tipo de cierre (1500 en DI650i, 2000 en DR412i) reinicia la secuencia.
2. Un aceite se reinicia en toda PM de tipo mayor o igual a su frecuencia.
3. Fecha proyectada = hoy + horas restantes / avance proyectado h/día (promedio real de las últimas 6 PM, o 13 h/día sin historial suficiente, + avance extra del 15 %).
4. Fecha sugerida = vencimiento proyectado − 15 % de los días restantes (redondeado hacia arriba), nunca anterior a hoy. «PROGRAMADA» exige una fecha igual o anterior a la sugerida; si es posterior queda «PROGRAMADA CON RIESGO».
5. Proyección: parte de la PM actual (fecha programada o proyectada) y suma 250 h por PM al ritmo del avance proyectado, siguiendo el ciclo del modelo.

# E2. Resumen de PM (PDF)
1. Botón «Resumen de PM (PDF)» en el Panel (Últimas PM) y en Historial. Primero pregunta el turno (Turno A o Turno B) y el período (por defecto los últimos 7 días).
2. El PDF incluye: puntos clave (PM ejecutadas, equipos, PM a tiempo / adelantadas / atrasadas, aceites cambiados, con atraso y pendientes), resumen por equipo, detalle de cada PM con su desviación en horas y en días, los aceites cambiados con su estado, y espacios de firma.
3. Desviación de la PM = horómetro real - (horómetro de la PM anterior + intervalo). «A tiempo» = dentro de la tolerancia (± horas) definida en Configuración. Un aceite está atrasado si sus horas acumuladas al cambio superan su frecuencia más la tolerancia.

# F. Proyección de aceites, aceites por semanas y kits
1. «Proyección aceites»: defina Desde / Hasta (dd-mm-aaaa) y presione «Definir período». El tramo anterior a hoy suma las PM ejecutadas del Historial y el tramo desde hoy, las PM proyectadas. LL-0006 se calcula por días calendario × litros por día.
2. «Exportar» genera un Excel con Resumen, Por equipo, Mes a mes, PM incluidas y Kits a solicitar.
3. «Aceites por semanas»: ① proyección anterior (desde y hasta, opcional), ② fecha de inicio de la proyección actual y ③ N° de semanas (1 a 52). «Exportar» genera Resumen, Necesidad neta, Semana a semana, PM incluidas y Kits a solicitar.
4. Inventario y pedidos (opcional): escriba por aceite el stock en bodega (litros), lo solicitado pendiente (tarros) y lo que viene en tránsito a faena (tarros). Si hay algún valor, tarros a pedir = (necesidad con margen − stock − (solicitado + tránsito) × litros por tarro) / litros por tarro. «Limpiar inventario» vuelve al cálculo con la proyección anterior.
4b. Necesidad neta: a lo pedido en la proyección anterior (tarros × litros por tarro) se le resta lo consumido desde su inicio hasta el día antes de la proyección actual; ese saldo se descuenta de la necesidad del nuevo plazo, para no volver a pedir aceite que ya estaba cubierto.
5. Precios: cada lubricante tiene un valor referencial por tarro (Configuración > Precios de lubricantes). Total $ = precio unitario × N° de tarros; aparece en Compra de aceites, Aceites por semanas y sus Excel.
6. «Kits a solicitar»: kits y repuestos sueltos del período por fechas y del plazo en semanas. Un kit por PM según modelo y tipo; repuestos sueltos = cantidad por PM × N° de PM.
7. «Kits PM» > «Exportar listado»: listado de repuestos sin duplicados con descripción, ubicación, dónde se usa y cantidad por tipo de PM.

# G. Administración
1. Historial y Aceites se pueden filtrar por equipo, editar (doble clic) y exportar a Excel.
2. «Reparar claves» recalcula las posiciones de ciclo de las PM mayores (se hace solo al editar). «Corregir fechas futuras» quita fechas de ejecución posteriores a hoy (deja nota en Observación).
3. «Recalcular horas acumuladas» rehace la columna de horas acumuladas al cambio de la tabla Aceites.
4. Configuración: parámetros, equipos, ciclos, tipos válidos, aceites, consumo por PM, consumo diario, kits y descripciones. «Importar datos desde Excel (.xlsm)» y «Restaurar respaldo (.db)» reemplazan los datos (con respaldo automático previo).
5. «Buscar actualizaciones» descarga e instala la última versión publicada; el programa se reinicia solo y los datos se conservan. Al abrir, si hay una versión nueva, se avisa en la barra lateral.
"""
