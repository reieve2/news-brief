' 静默运行项目里的 .bat，避免弹出黑色控制台窗口
' 用法：wscript run_hidden.vbs [延迟秒数] [bat 文件名]
'   wscript run_hidden.vbs 120 run_daily.bat
'   wscript run_hidden.vbs 180 run_weekly.bat
Dim fso, shell, here, delaySeconds, target
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
delaySeconds = 0
target = "run_daily.bat"
If WScript.Arguments.Count > 0 Then delaySeconds = CLng(WScript.Arguments(0))
If WScript.Arguments.Count > 1 Then target = WScript.Arguments(1)
If delaySeconds > 0 Then WScript.Sleep delaySeconds * 1000
shell.Run """" & here & "\" & target & """", 0, True
