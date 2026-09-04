@echo off
REM ---------------------------------------------------------------------
REM  oraculo.cmd - atalho do Oraculo (copiloto de FP&A)
REM  Uso:  oraculo.cmd <empresa> [--ia | --dash]
REM  Empresas: construtora-horizonte | fluxodata | rede-bompreco
REM ---------------------------------------------------------------------
setlocal
set "PROJ=%~dp0"
set "EMPRESA=%~1"
set "MODO=%~2"

if "%EMPRESA%"=="" goto :ajuda

set "DRE=%PROJ%dados\dre-%EMPRESA%.csv"
set "BAL=%PROJ%dados\balanco-%EMPRESA%.csv"
if not exist "%DRE%" goto :naoachei

REM --dash: gera o dashboard HTML (a SaaS so existe para a FluxoData)
if /I "%MODO%"=="--dash" (
  if /I "%EMPRESA%"=="fluxodata" (
    python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saas "%PROJ%dados\saas-fluxodata.csv"
  ) else (
    python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%"
  )
  exit /b %ERRORLEVEL%
)

REM --ia: narrativa escrita pela IA (consome credito). Sem flag: modo offline.
if /I "%MODO%"=="--ia" (
  python "%PROJ%src\copiloto.py" "%DRE%"
) else (
  python "%PROJ%src\copiloto.py" "%DRE%" --offline
)
exit /b %ERRORLEVEL%

:naoachei
echo ERRO: nao encontrei o arquivo "%DRE%"
echo Empresas disponiveis: construtora-horizonte, fluxodata, rede-bompreco
exit /b 1

:ajuda
echo Uso: oraculo.cmd [empresa] [--ia ^| --dash]
echo Empresas: construtora-horizonte, fluxodata, rede-bompreco
echo Sem flag = analise offline (deterministica, nao gasta credito de IA)
exit /b 1
