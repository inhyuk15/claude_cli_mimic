#!/usr/bin/env pwsh
Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD\src"
python src\core\orchestrator.py
