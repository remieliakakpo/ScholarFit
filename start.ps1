# Démarrage local sous Windows (PowerShell) : API (port 8000) + site (port 3000).
# Usage : clic droit > « Exécuter avec PowerShell », ou dans un terminal :
#   Set-ExecutionPolicy -Scope Process Bypass ; .\start.ps1
# "Continue" : sous Windows PowerShell 5.1, "Stop" fait planter le script dès qu'un
# programme écrit un simple avertissement. Chaque étape vérifie son code de sortie.
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$venvPy = Join-Path $backend ".venv\Scripts\python.exe"

function Fail($msg) {
  Write-Host ""
  Write-Host "ERREUR : $msg" -ForegroundColor Red
  Read-Host "Appuie sur Entrée pour fermer"
  exit 1
}
function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

# 1. Outils nécessaires
$python = $null
foreach ($c in @("python", "py")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    & $c -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = $c; break }
  }
}
if (-not $python) { Fail "Python 3.10 ou plus récent est introuvable. Installe-le depuis python.org (coche « Add python.exe to PATH »)." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "Node.js est introuvable. Installe la version LTS depuis nodejs.org." }

# 2. Environnement Python (réinstallé s'il est incomplet)
if (-not (Test-Path $venvPy)) {
  Step "Création de l'environnement Python"
  & $python -m venv (Join-Path $backend ".venv")
  if ($LASTEXITCODE -ne 0) { Fail "Impossible de créer backend\.venv." }
}
& $venvPy -c "import fastapi, uvicorn, sqlalchemy, pydantic_settings, jwt, httpx, bs4" 2>$null
if ($LASTEXITCODE -ne 0) {
  Step "Installation des dépendances Python (quelques minutes la première fois)"
  & $venvPy -m pip install --upgrade pip -q
  & $venvPy -m pip install -r (Join-Path $backend "requirements-dev.txt")
  if ($LASTEXITCODE -ne 0) { Fail "L'installation des dépendances Python a échoué (voir les messages ci-dessus)." }
}

# 3. Base de données : création ou mise à jour (sans doublons) à chaque démarrage
Step "Mise à jour de la base de bourses"
Push-Location $backend
& $venvPy -m app.cli seed
$seedCode = $LASTEXITCODE
Pop-Location
if ($seedCode -ne 0) { Fail "La préparation de la base a échoué. Si le problème continue, supprime backend\bourses.db puis relance." }

# 4. Dépendances du site
if (-not (Test-Path (Join-Path $frontend "node_modules\next"))) {
  Step "Installation des dépendances du site (quelques minutes la première fois)"
  Push-Location $frontend
  npm install --no-audit --no-fund
  $npmCode = $LASTEXITCODE
  Pop-Location
  if ($npmCode -ne 0) { Fail "npm install a échoué (voir les messages ci-dessus)." }
}

# 5. API dans sa propre fenêtre (on y voit les erreurs éventuelles)
$health = "http://127.0.0.1:8000/api/health"
$already = $false
try { Invoke-RestMethod $health -TimeoutSec 2 -ErrorAction Stop | Out-Null; $already = $true } catch {}
$api = $null
if ($already) {
  Write-Host "Une API tourne déjà sur le port 8000 : on la réutilise." -ForegroundColor Yellow
} else {
  $busy = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  if ($busy) { Fail "Le port 8000 est déjà pris par un autre programme (PID $($busy[0].OwningProcess)). Ferme-le puis relance." }
  Step "Démarrage de l'API (fenêtre « API ScholarFit »)"
  $cmd = "`$host.UI.RawUI.WindowTitle = 'API ScholarFit'; Set-Location '$backend'; & '$venvPy' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  $api = Start-Process powershell -PassThru -ArgumentList "-NoExit", "-NoProfile", "-Command", $cmd
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-RestMethod $health -TimeoutSec 2 -ErrorAction Stop | Out-Null; $ok = $true; break } catch {}
    if ($api.HasExited) { break }
  }
  if (-not $ok) { Fail "L'API ne démarre pas. Regarde le message d'erreur dans la fenêtre « API ScholarFit »." }
}
Write-Host "API prête : http://127.0.0.1:8000/docs" -ForegroundColor Green

# 6. Site
Step "Démarrage du site : ouvre http://localhost:3000"
$env:API_URL_INTERNAL = "http://127.0.0.1:8000"
Remove-Item Env:NEXT_PUBLIC_API_URL -ErrorAction SilentlyContinue
Push-Location $frontend
try {
  npm run dev -- -p 3000
} finally {
  Pop-Location
  if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
}
