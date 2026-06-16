@echo off
cd /d "C:\Users\hankwu\Desktop\Event_Center\CF\rule"
python "C:\Users\hankwu\Desktop\Event_Center\CF\rule\auto_activity_pixel.py" > "C:\Users\hankwu\Desktop\Event_Center\CF\rule\run_log_20260616.txt" 2>&1
echo EXITCODE %errorlevel% >> "C:\Users\hankwu\Desktop\Event_Center\CF\rule\run_log_20260616.txt"
