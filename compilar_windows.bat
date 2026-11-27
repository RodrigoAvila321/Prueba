@echo off
REM Compila PlanificacionPM.exe (requiere Python 3.10 o superior instalado desde python.org)
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -c "from planificacion_pm.tema import guardar_ico; guardar_ico('icono.ico')"
python -c "from planificacion_pm.splash import guardar_png; guardar_png('splash.png')"
pyinstaller --noconfirm --onefile --windowed --icon icono.ico --splash splash.png --hidden-import PIL._tkinter_finder --name PlanificacionPM main.py
echo.
echo Listo: el ejecutable quedo en la carpeta dist\PlanificacionPM.exe
pause
