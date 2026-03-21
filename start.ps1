# Stock Predict - Start Backend + Frontend
Write-Host "Starting Stock Predict..." -ForegroundColor Cyan

# Start Backend
Write-Host "Starting Backend (FastAPI) on port 8000..." -ForegroundColor Yellow
$backend = Start-Process powershell -ArgumentList "-NoProfile -Command cd backend; ..\venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000" -PassThru -WindowStyle Normal

Start-Sleep -Seconds 3

# Start Frontend
Write-Host "Starting Frontend (Next.js) on port 3000..." -ForegroundColor Yellow
$frontend = Start-Process powershell -ArgumentList "-NoProfile -Command cd frontend; npm run dev" -PassThru -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to stop both servers..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Stop-Process $backend -ErrorAction SilentlyContinue
Stop-Process $frontend -ErrorAction SilentlyContinue
Write-Host "Stopped." -ForegroundColor Red
