@echo off
REM ---------------------------------------------------------------------
REM  publicar.cmd - fecha a Trilha 1 do curso.
REM  Roda os testes, commita, envia ao GitHub, escreve descricao e topicos
REM  e (com confirmacao) abre o repositorio ao publico.
REM  Uso:  .\publicar.cmd
REM ---------------------------------------------------------------------
setlocal
set "REPO=kerlisonalbert/fin-copiloto-fpa"
cd /d "%~dp0"

echo.
echo ================= 1/5  O que ainda nao foi enviado =================
git status --short
echo.

echo ================= 2/5  Testes (portao de qualidade) ================
python -m pytest -q
if errorlevel 1 (
  echo.
  echo ABORTADO: os testes falharam. NADA foi publicado.
  echo Corrija antes de continuar - commit que quebra teste vira historico.
  exit /b 1
)
echo.

echo ================= 3/5  Commit e envio ==============================
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Genericiza o caminho local na copia versionada do TOOLS.md"
) else (
  echo Nada novo para commitar - seguindo.
)
git push
if errorlevel 1 (
  echo ABORTADO: o push falhou. Confira a conexao e o 'gh auth status'.
  exit /b 1
)
echo.

echo ================= 4/5  Descricao e topicos =========================
gh repo edit %REPO% --description "Copiloto de FP&A com IA no Telegram: analise de desvios, ~30 indicadores, DFC e dashboard. Os numeros vem do codigo, a narrativa vem da IA."
gh repo edit %REPO% --add-topic fpa,financial-analysis,ai-agents,controladoria,python,telegram-bot,dashboard,data-governance,llm
echo.

echo ================= 5/5  Abrir ao publico ============================
echo.
echo   ATENCAO - este passo e irreversivel na pratica.
echo   Depois de publico, o conteudo pode ser clonado, indexado por
echo   buscadores e copiado. Voltar a privado NAO apaga o que ja saiu.
echo.
echo   A varredura ja foi feita: nenhuma chave, token ou identificador
echo   pessoal nos 38 arquivos versionados. A pasta dados\minhas esta
echo   fora do Git.
echo.
set "RESP="
set /p RESP=Digite PUBLICAR para confirmar (qualquer outra coisa cancela): 
if /I not "%RESP%"=="PUBLICAR" (
  echo.
  echo Cancelado. O repositorio continua PRIVADO. Nada mais foi alterado.
  exit /b 0
)
gh repo edit %REPO% --visibility public --accept-visibility-change-consequences
if errorlevel 1 (
  echo Falhou ao alterar a visibilidade. O repositorio continua privado.
  exit /b 1
)
echo.
echo ===================================================================
echo  PUBLICADO:  https://github.com/%REPO%
echo ===================================================================
gh repo view %REPO% --json name,visibility,description,repositoryTopics
exit /b 0
