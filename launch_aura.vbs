Option Explicit

Dim shell, fileSystem, rootPath, pythonExe, command

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

rootPath = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExe = rootPath & "\.venv\Scripts\pythonw.exe"

If Not fileSystem.FileExists(pythonExe) Then
    pythonExe = "pythonw.exe"
End If

shell.CurrentDirectory = rootPath
shell.Environment("PROCESS")("PYTHONPATH") = rootPath & "\src"
shell.Environment("PROCESS")("AURA_DEMO_MODE") = "true"
shell.Environment("PROCESS")("AURA_DEMO_WORKSPACE") = "DemoWorkspace"

command = Chr(34) & pythonExe & Chr(34) & " -m aura.main"
shell.Run command, 0, False
