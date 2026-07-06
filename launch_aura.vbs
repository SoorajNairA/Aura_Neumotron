Option Explicit

Dim shell, fileSystem, rootPath, pythonExe, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
rootPath = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExe = rootPath & "\.venv\Scripts\pythonw.exe"
If Not fileSystem.FileExists(pythonExe) Then pythonExe = "pythonw.exe"
shell.CurrentDirectory = rootPath
shell.Environment("PROCESS")("PYTHONPATH") = rootPath & "\src"
command = Chr(34) & pythonExe & Chr(34) & " -m aura.legacy.assistant.main"
shell.Run command, 0, False
