# 装启动项：登录后跑早报，再晚一点检查周报。
#
# 只装周报：早报交给云端 GitHub Actions 每天 07:00 跑，本地再挂一个登录触发会撞车。
# 路径只在装的时候写进启动文件夹的快捷方式里，仓库本身不含任何本机路径。
# 22:30 那个本地兜底任务已经不在这里注册了——云端 GitHub Actions 出早报、
# local_fallback 负责补跑，两边重复会白花钱。
#
# 用法：powershell -ExecutionPolicy Bypass -File tools\install_tasks.ps1

param([switch]$WithFallbackTask)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root "run_hidden.vbs"
$startup = [Environment]::GetFolderPath("Startup")
$ws = New-Object -ComObject WScript.Shell

function New-StartupLink($name, $arguments, $description) {
    $path = Join-Path $startup $name
    $link = $ws.CreateShortcut($path)
    $link.TargetPath = "wscript.exe"
    $link.Arguments = $arguments
    $link.WorkingDirectory = $root
    $link.Description = $description
    $link.Save()
    Write-Host "启动项已创建: $path"
}

New-StartupLink "AI-Brief-Weekly.lnk" "`"$launcher`" 180 run_weekly.bat" "每周 AI 周报"

if ($WithFallbackTask) {
    $action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`" 0 run_daily.bat"
    $daily = New-ScheduledTaskTrigger -Daily -At 22:30
    Register-ScheduledTask -TaskName "AI-Brief-Daily" -Action $action -Trigger $daily -Force | Out-Null
    Write-Host "已注册每天 22:30 的本地兜底任务"
}
