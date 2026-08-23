@echo off
chcp 65001 > nul

:: Muda para o diretorio raiz do projeto
cd /d "%~dp0"

echo.
echo  NetTRAC NF Watcher — Inicio manual
echo  -----------------------------------
echo  Monitorando a pasta pdfs\ e xmls\
echo  Esta janela pode ser MINIMIZADA (nao feche).
echo  Pressione Ctrl+C para encerrar.
echo.

python scripts\watcher.py

echo.
echo  Watcher encerrado.
pause
