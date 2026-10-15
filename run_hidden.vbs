' 静默运行 run_daily.bat，避免弹出一个黑色控制台窗口
' 可带一个参数表示延迟秒数：wscript run_hidden.vbs 120
Dim fso, shell, here, delaySeconds
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
delaySeconds = 0
If WScript.Arguments.Count > 0 Then delaySeconds = CLng(WScript.Arguments(0))
If delaySeconds > 0 Then WScript.Sleep delaySeconds * 1000
shell.Run """" & here & "\run_daily.bat""", 0, True
