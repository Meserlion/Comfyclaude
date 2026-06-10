@echo off
cd /d "%~dp0"
echo Testing ComfyUI image generation...
python comfyui_generate.py "a cute orange cat sitting on a windowsill, digital art" --steps 9 --width 512 --height 512 > _generate_output.txt 2>&1
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS > _generate_status.txt
) else (
    echo FAILED > _generate_status.txt
)
type _generate_output.txt
pause
