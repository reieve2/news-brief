# 两处触发：
#   1) 登录后延迟 2 分钟跑一次（放启动文件夹，不需要管理员权限）
#   2) 每天 22:30 兜底跑一次（计划任务）
# 用法：powershell -ExecutionPolicy Bypass -File tools\install_tasks.ps1

$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "run_hidden.vbs"

# 1) 启动文件夹快捷方式
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$linkPath = Join-Path $startup "AI-Brief.lnk"
$ws = New-Object -ComObject WScript.Shell
$link = $ws.CreateShortcut($linkPath)
$link.TargetPath = "wscript.exe"
$link.Arguments = "`"$script`" 120"
$link.WorkingDirectory = $root
$link.Description = "每日 AI 科技早报"
$link.Save()
Write-Host "启动项已创建: $linkPath"

# 2) 每天 22:30 的兜底任务
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$script`""
$daily = New-ScheduledTaskTrigger -Daily -At 22:30
Register-ScheduledTask -TaskName "AI-Brief-Daily" -Action $action -Trigger $daily -Force | Out-Null

Get-ScheduledTask -TaskName "AI-Brief-*" | Select-Object TaskName, State | Format-Table -AutoSize
Get-ScheduledTaskInfo -TaskName "AI-Brief-Daily" | Select-Object TaskName, NextRunTime | Format-Table -AutoSize
