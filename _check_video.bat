@echo off
cd /d "%~dp0"
python _check_video.py > _check_video_output.txt 2>&1
echo DONE > _check_video_status.txt
