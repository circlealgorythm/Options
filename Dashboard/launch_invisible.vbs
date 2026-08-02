Set WshShell = CreateObject("WScript.Shell")
Set FileSystem = CreateObject("Scripting.FileSystemObject")
ScriptDir = FileSystem.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd.exe /c """ & ScriptDir & "\start_dashboard.bat""", 0, False
