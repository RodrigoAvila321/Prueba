@echo off
REM Compila PlanificacionPM.exe (requiere Python 3.10 o superior instalado desde python.org)
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -c "from planificacion_pm.tema import guardar_ico; guardar_ico('icono.ico')"
pyinstaller --noconfirm --onefile --windowed --icon icono.ico --name PlanificacionPM main.py
echo.
echo Listo: el ejecutable quedo en la carpeta dist\PlanificacionPM.exe
pause
