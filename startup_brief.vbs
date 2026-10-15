' 放在「启动」文件夹里：登录后延迟 2 分钟，静默生成早报
Dim shell
Set shell = CreateObject("WScript.Shell")
WScript.Sleep 120000
shell.Run """D:\Desktop\2\news-brief\run_daily.bat""", 0, True
