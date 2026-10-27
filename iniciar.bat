@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
title Baixador de Musicas e Videos

rem --- 1. Achar o Python ---------------------------------------------------
set "PY="
if exist ".venv\Scripts\python.exe" goto :venv_ok
for %%P in (python.exe) do if not "%%~$PATH:P"=="" (
    "%%~$PATH:P" --version >nul 2>&1 && set "PY=%%~$PATH:P"
)
if not defined PY (
    where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set "PY=%%D\python.exe"
    )
)
if not defined PY (
    echo Python nao encontrado. Instalando pelo winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set "PY=%%D\python.exe"
    )
)
if not defined PY (
    echo.
    echo Nao consegui instalar o Python. Baixe em https://www.python.org/downloads/
    pause
    exit /b 1
)

rem --- 2. Criar o ambiente virtual na primeira vez -------------------------
echo Preparando o ambiente (so demora na primeira vez)...
if "%PY:~0,2%"=="py" (%PY% -m venv .venv) else ("%PY%" -m venv .venv)
if errorlevel 1 (
    echo Falha ao criar o ambiente virtual.
    pause
    exit /b 1
)

:venv_ok
rem --- 3. Instalar/atualizar o yt-dlp (sites mudam, manter atualizado) -----
echo Atualizando o yt-dlp...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -U -r requirements.txt
if errorlevel 1 (
    echo Aviso: nao consegui atualizar as dependencias. Tentando abrir mesmo assim...
)

rem --- 4. FFmpeg (necessario para MP3 e para juntar video+audio) -----------
where ffmpeg >nul 2>&1
if errorlevel 1 (
    dir /s /b "%LOCALAPPDATA%\Microsoft\WinGet\Packages\*ffmpeg.exe" >nul 2>&1
    if errorlevel 1 (
        echo FFmpeg nao encontrado. Instalando pelo winget...
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    )
)

rem --- 5. Abrir o programa -------------------------------------------------
start "" ".venv\Scripts\pythonw.exe" baixador.py
endlocal
