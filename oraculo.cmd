@echo off
REM ---------------------------------------------------------------------
REM  oraculo.cmd - atalho do Oraculo (copiloto de FP&A)
REM  Uso:  oraculo.cmd <empresa> [--ia | --dash]
REM  Empresas: construtora-horizonte | fluxodata | rede-bompreco
REM
REM  --dash grava o HTML e tambem um PNG (renderizado por Edge/Chrome headless)
REM  numa pasta SEM ESPACOS, porque a camada de anexo do OpenClaw quebra
REM  caminhos com espaco e so entrega imagem/audio/video como "media".
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
set "PNG=%OUTDIR%\relatorio-%EMPRESA%.png"

if /I "%EMPRESA%"=="fluxodata" (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saas "%PROJ%dados\saas-fluxodata.csv" --saida "%SAIDA%"
) else (
  python "%PROJ%src\gerar_relatorio.py" "%DRE%" "%BAL%" --saida "%SAIDA%"
)
if errorlevel 1 exit /b 1
copy /Y "%SAIDA%" "%PROJ%exemplos\relatorio-%EMPRESA%.html" >nul

REM --- procura um navegador para gerar a imagem (opcional) ---
set "NAV="
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "NAV=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined NAV if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "NAV=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined NAV if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "NAV=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined NAV if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "NAV=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined NAV goto :sem_imagem

REM converte C:\a\b para file:///C:/a/b
set "URL=file:///%SAIDA:\=/%"
"%NAV%" --headless=new --disable-gpu --hide-scrollbars --window-size=1400,3950 --virtual-time-budget=4000 --screenshot="%PNG%" "%URL%" >nul 2>&1
if not exist "%PNG%" goto :sem_imagem
echo Imagem gerada: %PNG%
exit /b 0

:sem_imagem
echo AVISO: nao foi possivel gerar a imagem PNG (navegador nao encontrado). Apenas o HTML foi criado.
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
