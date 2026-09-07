$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tool = Join-Path $scriptDir "cicd_setup.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $tool @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $tool @args
    exit $LASTEXITCODE
}

throw "Python was not found. Install Python 3 to run the CI/CD setup tool."
