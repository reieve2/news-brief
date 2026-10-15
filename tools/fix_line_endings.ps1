# 把 .bat 和 .vbs 统一改成 CRLF 换行——cmd 和 wscript 都不认 LF 换行
$files = @(
    "run_daily.bat",
    "run_hidden.vbs",
    "startup_brief.vbs"
)
$root = Split-Path -Parent $PSScriptRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)

foreach ($name in $files) {
    $path = Join-Path $root $name
    if (-not (Test-Path $path)) { continue }
    $text = [System.IO.File]::ReadAllText($path)
    $text = $text.Replace("`r`n", "`n").Replace("`n", "`r`n")
    [System.IO.File]::WriteAllText($path, $text, $utf8)
    Write-Host "已修正换行: $path"
}
