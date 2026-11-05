# Thin compatibility wrapper. Setup and process lifecycle live in the npm scripts.
Set-Location $PSScriptRoot
npm run dev:all
exit $LASTEXITCODE
