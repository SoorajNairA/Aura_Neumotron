@echo off
setlocal
cd /d "%~dp0"

set "AURA_DEMO_MODE=true"
set "AURA_DEMO_WORKSPACE=DemoWorkspace"

rem Demo settings are inherited by the hidden VBS launcher.
wscript.exe //nologo "%~dp0launch_aura.vbs"
exit /b 0
