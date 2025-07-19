@echo off
REM build.bat – escolha qual build executar: onedir, onefile ou ambos

REM Ajusta para o diretório onde o script está
cd /d "%~dp0"

echo ==============================================
echo  TestAI Build Script
echo ==============================================
echo 1) Gerar Onedir (pasta + _internal)
echo 2) Gerar Onefile (unico EXE)
echo 3) Gerar Ambos
echo.
set /p escolha=Escolha uma opcao [1-3]:

if "%escolha%"=="1" goto onedir
if "%escolha%"=="2" goto onefile
if "%escolha%"=="3" goto ambos

echo Opcao invalida. Saindo...
goto fim

:onedir
echo.
echo [1] Gerando Onedir...
pyinstaller --clean --noconfirm TestAI_onedir.spec
goto fim

:onefile
echo.
echo [2] Gerando Onefile...
pyinstaller --clean --noconfirm TestAI.spec
goto fim

:ambos
echo.
echo [1] Gerando Onedir...
pyinstaller --clean --noconfirm TestAI_onedir.spec

echo.
echo [2] Gerando Onefile...
pyinstaller --clean --noconfirm TestAI.spec
goto fim

:fim
echo.
echo Build(s) concluido(s).
pause
