@echo off
cd /d "%~dp0"
python _make_loop.py > _make_loop_output.txt 2>&1
if %ERRORLEVEL% EQU 0 (echo SUCCESS > _make_loop_status.txt) else (echo FAILED > _make_loop_status.txt)
