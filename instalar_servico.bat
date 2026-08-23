@echo off

echo.
echo  ============================================================
echo    NetTRAC NF Watcher - Instalacao
echo  ============================================================
echo.

:: Diretorio do projeto (onde este .bat esta localizado)
set "PROJETO=%~dp0"
if "%PROJETO:~-1%"=="\" set "PROJETO=%PROJETO:~0,-1%"

echo  Projeto : %PROJETO%
echo.

:: ============================================================
:: 1. Instalar dependencias
:: ============================================================
echo  [1/4] Instalando dependencias Python...
echo.

pip install -r "%PROJETO%\requirements.txt"

if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERRO: Falha ao instalar dependencias.
    echo  Certifique-se de que Python e pip estao no PATH.
    pause
    exit /b 1
)

echo.
echo  Dependencias instaladas com sucesso.
echo.

:: ============================================================
:: 2. Criar pastas necessarias
:: ============================================================
echo  [2/4] Criando pastas necessarias...

if not exist "%PROJETO%\pdfs\processados" mkdir "%PROJETO%\pdfs\processados"
if not exist "%PROJETO%\pdfs\erros"       mkdir "%PROJETO%\pdfs\erros"
if not exist "%PROJETO%\xmls\processados" mkdir "%PROJETO%\xmls\processados"
if not exist "%PROJETO%\xmls\erros"       mkdir "%PROJETO%\xmls\erros"
if not exist "%PROJETO%\logs"             mkdir "%PROJETO%\logs"

echo  Pastas criadas com sucesso.
echo.

:: ============================================================
:: 3. Localizar python.exe
:: ============================================================
echo  [3/4] Localizando Python...

set "PYTHONEXE="
for /f "tokens=*" %%i in ('where pythonw.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%i"
if not defined PYTHONEXE (
    for /f "tokens=*" %%i in ('where python.exe 2^>nul') do if not defined PYTHONEXE set "PYTHONEXE=%%i"
)

if not defined PYTHONEXE (
    echo  ERRO: Python nao encontrado no PATH.
    echo  Instale o Python em https://python.org e marque "Add to PATH".
    pause
    exit /b 1
)

echo  Python encontrado: %PYTHONEXE%
echo.

:: ============================================================
:: 4. Criar atalho na pasta Startup do usuario
::    (inicia automaticamente ao login, sem precisar de admin)
:: ============================================================
echo  [4/4] Configurando inicio automatico com o Windows...

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "ATALHO=%STARTUP%\NetTRAC_NF_Watcher.bat"

:: Cria um .bat launcher na pasta Startup
(
    echo @echo off
    echo cd /d "%PROJETO%"
    echo start "" "%PYTHONEXE%" "%PROJETO%\scripts\watcher.py"
) > "%ATALHO%"

if %ERRORLEVEL% neq 0 (
    echo  ERRO: Nao foi possivel criar o atalho de inicializacao.
    pause
    exit /b 1
)

echo  Atalho criado em:
echo    %ATALHO%
echo.

:: ============================================================
:: Conclusao
:: ============================================================
echo  ============================================================
echo    Instalacao concluida com sucesso!
echo  ============================================================
echo.
echo  O watcher vai iniciar automaticamente toda vez
echo  que o Windows for ligado. Nao precisa fazer mais nada.
echo.
echo  Onde jogar os arquivos:
echo    PDFs -^> %PROJETO%\pdfs\
echo    XMLs -^> %PROJETO%\xmls\
echo.
echo  Apos processar, os arquivos vao para:
echo    Sucesso -^> pdfs\processados\  ou  xmls\processados\
echo    Erro    -^> pdfs\erros\        ou  xmls\erros\
echo.
echo  Log completo:
echo    %PROJETO%\logs\watcher.log
echo.
echo  Para iniciar agora sem reiniciar o Windows:
echo    Execute  iniciar_watcher.bat
echo.
pause
