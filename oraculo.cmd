@echo off
REM ---------------------------------------------------------------------
REM  oraculo.cmd - atalho do Oraculo (copiloto de FP&A)
REM  Uso:  oraculo.cmd <empresa> [--ia | --dash]
REM
REM  <empresa> pode ser:
REM    - uma demo:      construtora-horizonte | fluxodata | rede-bompreco
REM    - a SUA empresa: qualquer nome, desde que exista
REM                     dados\minhas\dre-<nome>.csv   (e opcionalmente
REM                     dados\minhas\balanco-<nome>.csv para o --dash)
REM
REM  A pasta dados\minhas esta no .gitignore: dado real NUNCA vai pro GitHub.
REM ---------------------------------------------------------------------
setlocal
set "PROJ=%~dp0"
set "EMPRESA=%~1"
set "MODO=%~2"
set "OUTDIR=%USERPROFILE%\.openclaw\workspace\relatorios"

if "%EMPRESA%"=="" goto :ajuda

REM 1) procura nas demos
set "DRE=%PROJ%dados\dre-%EMPRESA%.csv"
set "BAL=%PROJ%dados\balanco-%EMPRESA%.csv"
if exist "%DRE%" goto :achou

REM 2) procura nas SUAS planilhas
set "DRE=%PROJ%dados\minhas\dre-%EMPRESA%.csv"
set "BAL=%PROJ%dados\minhas\balanco-%EMPRESA%.csv"
if exist "%DRE%" goto :achou

goto :naoachei

:achou
if /I "%MODO%"=="--dash" goto :dash
if /I "%MODO%"=="--ia"   goto :ia

REM padrao: analise offline (deterministica, nao gasta credito de IA)
python "%PROJ%src\copiloto.py" "%DRE%" --offline
exit /b %ERRORLEVEL%

:ia
python "%PROJ%src\copiloto.py" "%DRE%"
exit /b %ERRORLEVEL%

:dash
if not exist "%BAL%" goto :sem_balanco
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
set "SAIDA=%OUTDIR%\relatorio-%EMPRESA%.html"
set "PNG=%OUTDIR%\relatorio-%EMPRESA%.png"

if /I "%EMPRESA%"=="fluxodata" (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saas "%PROJ%dados\saas-fluxodata.csv" --saida "%SAIDA%"
) else (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saida "%SAIDA%"
)
if errorlevel 1 exit /b 1
if exist "%PROJ%dados\dre-%EMPRESA%.csv" copy /Y "%SAIDA%" "%PROJ%exemplos\relatorio-%EMPRESA%.html" >nul

REM --- procura um navegador para gerar a imagem (opcional) ---
set "NAV="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "NAV=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined NAV if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "NAV=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined NAV if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "NAV=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined NAV if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "NAV=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined NAV goto :sem_imagem

set "URL=file:///%SAIDA:\=/%"
"%NAV%" --headless=new --disable-gpu --hide-scrollbars --window-size=1400,3950 --virtual-time-budget=4000 --screenshot="%PNG%" "%URL%" >nul 2>&1
if not exist "%PNG%" goto :sem_imagem
echo Imagem gerada: %PNG%
exit /b 0

:sem_imagem
echo AVISO: nao foi possivel gerar a imagem PNG (navegador nao encontrado). Apenas o HTML foi criado.
exit /b 0

:sem_balanco
echo ERRO: o --dash precisa tambem do balanco: "%BAL%"
echo Use dados\MODELO-balanco.csv como modelo. Sem balanco, rode sem a flag --dash
echo (a analise de orcado x realizado funciona so com a DRE).
exit /b 1

:naoachei
echo ERRO: nao encontrei planilha para "%EMPRESA%".
echo.
echo Demos disponiveis: construtora-horizonte, fluxodata, rede-bompreco
echo.
echo Para usar SUA planilha, salve como:
echo   %PROJ%dados\minhas\dre-%EMPRESA%.csv
echo   %PROJ%dados\minhas\balanco-%EMPRESA%.csv   (opcional, para o --dash)
echo Modelo em: %PROJ%dados\MODELO-dre.csv
exit /b 1

:ajuda
echo Uso: oraculo.cmd [empresa] [--ia ^| --dash]
echo Demos: construtora-horizonte, fluxodata, rede-bompreco
echo Suas planilhas: dados\minhas\dre-[nome].csv  (veja dados\minhas\LEIA-ME.md)
echo Sem flag = analise offline (deterministica, nao gasta credito de IA)
exit /b 1
