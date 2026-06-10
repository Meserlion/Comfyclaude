@echo off
cd /d "%~dp0"
echo Running ComfyUI generation...
python comfyui_generate.py %* > _generate_output.txt 2>&1
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS > _generate_status.txt
) else (
    echo FAILED > _generate_status.txt
)
type _generate_output.txt
