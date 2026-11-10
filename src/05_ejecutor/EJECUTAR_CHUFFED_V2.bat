@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Chuffed V2 (modelo con cotas y búsqueda) - NO CERRAR ESTA VENTANA
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo No se encontro Python 3.9 o superior.
  pause
  exit /b 1
)
%PY% ejecutor.py --bloques 0_humo D_chuffed_v2 --a-la-vez 2 --afinidad %*
echo.
pause
