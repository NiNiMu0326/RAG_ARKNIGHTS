Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Start backend (hidden, no window)
WshShell.Run "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000", 0, False

' Wait for backend to initialize
WScript.Sleep 3000

' Start frontend (hidden, no window)
WshShell.Run "cmd /c cd /d """ & WshShell.CurrentDirectory & "\frontend"" && npx vite --port 8889", 0, False
