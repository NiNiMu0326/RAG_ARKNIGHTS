Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "taskkill /f /im python.exe", 0, True
WshShell.Run "taskkill /f /im node.exe", 0, True
