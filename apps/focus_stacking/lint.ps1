# lint.ps1

Write-Host "Running Black..."
python -m black .

Write-Host "`nRunning Flake8..."
python -m flake8 .

Write-Host "`nRunning MyPy..."
python -m mypy src/