@echo off
chcp 65001 >nul
title Prospeccao MEI - preparando dados
cd /d "%~dp0"
echo.
echo  Prospeccao MEI - baixando a base da Receita e separando os MEIs do MA.
echo  Isso demora (sao uns 7 GB). Pode minimizar esta janela.
echo  O andamento fica no arquivo progresso.txt nesta pasta.
echo.

set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo  Python nao encontrado. Instalando o Python 3.12...
  echo Instalando Python > progresso.txt
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo  Nao consegui instalar o Python. Instale em python.org e rode de novo.
  echo ERRO: sem Python >> progresso.txt
  pause
  exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "UFS=MA"
if not "%~1"=="" set "UFS=%*"
%PY% -u preparar_dados.py --uf %UFS% --pasta receita --saida dados_gerados > progresso.txt 2>&1
if errorlevel 1 (
  echo ERRO >> progresso.txt
  echo  Deu erro. Veja o arquivo progresso.txt.
  pause
  exit /b 1
)
echo FIM-OK >> progresso.txt
echo.
echo  Pronto! Os dados estao em dados_gerados. Pode fechar esta janela.
pause
