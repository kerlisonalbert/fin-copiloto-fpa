@echo off
REM ---------------------------------------------------------------------
REM  oraculo.cmd - atalho do Oraculo (copiloto de FP&A)
REM  Uso:  oraculo.cmd <empresa> [--ia | --dash]
REM  Empresas: construtora-horizonte | fluxodata | rede-bompreco
REM
REM  O dashboard e gravado em uma pasta SEM ESPACOS
REM  (%USERPROFILE%\.openclaw\workspace\relatorios) porque a camada de anexo
REM  do OpenClaw quebra caminhos com espaco. Uma copia vai para exemplos/.
REM ---------------------------------------------------------------------
setlocal
set "PROJ=%~dp0"
set "EMPRESA=%~1"
set "MODO=%~2"
set "OUTDIR=%USERPROFILE%\.openclaw\workspace\relatorios"

if "%EMPRESA%"=="" goto :ajuda

set "DRE=%PROJ%dados\dre-%EMPRESA%.csv"
set "BAL=%PROJ%dados\balanco-%EMPRESA%.csv"
if not exist "%DRE%" goto :naoachei

if /I "%MODO%"=="--dash" goto :dash
if /I "%MODO%"=="--ia"   goto :ia

REM padrao: analise offline (deterministica, nao gasta credito de IA)
python "%PROJ%src\copiloto.py" "%DRE%" --offline
exit /b %ERRORLEVEL%

:ia
python "%PROJ%src\copiloto.py" "%DRE%"
exit /b %ERRORLEVEL%

:dash
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
set "SAIDA=%OUTDIR%\relatorio-%EMPRESA%.html"
if /I "%EMPRESA%"=="fluxodata" (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saas "%PROJ%dados\saas-fluxodata.csv" --saida "%SAIDA%"
) else (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saida "%SAIDA%"
)
if errorlevel 1 exit /b 1
copy /Y "%SAIDA%" "%PROJ%exemplos\relatorio-%EMPRESA%.html" >nul
exit /b 0

:naoachei
echo ERRO: nao encontrei o arquivo "%DRE%"
echo Empresas disponiveis: construtora-horizonte, fluxodata, rede-bompreco
exit /b 1

:ajuda
echo Uso: oraculo.cmd [empresa] [--ia ^| --dash]
echo Empresas: construtora-horizonte, fluxodata, rede-bompreco
echo Sem flag = analise offline (deterministica, nao gasta credito de IA)
exit /b 1
