@echo off
setlocal
cd /d "%~dp0"

rem The VBS handoff launches pythonw with no persistent console window.
wscript.exe //nologo "%~dp0launch_aura.vbs"
exit /b 0
