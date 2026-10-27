@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Compilando Baixador.exe

rem Gera dist\Baixador.exe: um arquivo só, com o Python e todas as bibliotecas dentro.
rem FFmpeg e Deno ficam de fora (são grandes); o .exe oferece instalar na primeira vez.

if not exist ".venv\Scripts\python.exe" (
    echo Rode o iniciar.bat uma vez antes, para preparar o ambiente.
    pause
    exit /b 1
)

echo Atualizando o yt-dlp e o PyInstaller...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -U -r requirements.txt pyinstaller
if errorlevel 1 goto :erro

echo Compilando (leva alguns minutos)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Baixador --icon icone.ico --add-data "icone.ico;." ^
    --collect-data yt_dlp_ejs --collect-submodules gallery_dl baixador.py
if errorlevel 1 goto :erro

echo.
echo Pronto: %~dp0dist\Baixador.exe
pause
exit /b 0

:erro
echo.
echo A compilacao falhou. Veja as mensagens acima.
pause
exit /b 1
