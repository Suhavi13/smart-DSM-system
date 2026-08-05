$ErrorActionPreference = "Stop"

if (-not (Test-Path "backend\app\models.py")) {
    throw "Run this script from the DSM_project root folder."
}

Write-Host "Checking the patched Python files..." -ForegroundColor Cyan
python -m py_compile `
    backend\app\models.py `
    backend\app\schemas.py `
    backend\app\recommendation_repository.py `
    backend\app\routers\recommendations.py `
    backend\app\routers\decisions.py `
    backend\migrate_recommendation_storage.py

Write-Host "Updating the PostgreSQL recommendation tables..." -ForegroundColor Cyan
python backend\migrate_recommendation_storage.py

Write-Host "Recommendation storage is ready." -ForegroundColor Green
Write-Host "Restart FastAPI, sign in as an Operator, and open the Recommendations page."
