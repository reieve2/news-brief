# 把根目录下的 .bat 和 .vbs 统一改成 CRLF 换行——cmd 和 wscript 都不认 LF 换行
$root = Split-Path -Parent $PSScriptRoot
$files = Get-ChildItem -Path $root -File |
    Where-Object { $_.Extension -in ".bat", ".vbs" } |
    ForEach-Object { $_.Name }
$utf8 = New-Object System.Text.UTF8Encoding($false)

foreach ($name in $files) {
    $path = Join-Path $root $name
    if (-not (Test-Path $path)) { continue }
    $text = [System.IO.File]::ReadAllText($path)
    $text = $text.Replace("`r`n", "`n").Replace("`n", "`r`n")
    [System.IO.File]::WriteAllText($path, $text, $utf8)
    Write-Host "已修正换行: $path"
}
