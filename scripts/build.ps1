param(
    [ValidateSet("onedir", "onefile")]
    [string]$Mode = "onedir"
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

$fontCandidates = Get-ChildItem -Path $projectRoot -Filter *.ttf -File
if (-not $fontCandidates) {
    throw "No .ttf file found in project root. Put your DM font file in root before building."
}

$fontFile = $fontCandidates |
    Sort-Object @{
        Expression = {
            $n = $_.Name.ToLowerInvariant()
            if ($n -match "dm.*mono") { 0 }
            elseif ($n.StartsWith("dm")) { 1 }
            else { 2 }
        }
    }, Name |
    Select-Object -First 1

Write-Host "Using font file:" $fontFile.Name

$modeArg = if ($Mode -eq "onefile") { "--onefile" } else { "--onedir" }
$addData = "{0};review_trash/assets/fonts" -f $fontFile.FullName

uv run pyinstaller review_trash/__main__.py `
    --name ReviewTrash `
    --windowed `
    $modeArg `
    --clean `
    --noconfirm `
    --add-data $addData
