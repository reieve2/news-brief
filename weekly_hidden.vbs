' 登录后延迟 3 分钟检查周报：只在需要时生成，不做就一秒退出
Dim shell
Set shell = CreateObject("WScript.Shell")
WScript.Sleep 180000
shell.Run """D:\Desktop\2\news-brief\run_weekly.bat""", 0, True
