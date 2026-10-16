@echo off
REM Agent Bot — o'z-o'zini qayta yondiradigan ishga tushirgich.
REM Deraza yopilmasa, bot o'lsa 10 soniyada qayta yonadi. Log: logs\bot.log
cd /d C:\Users\user\Desktop\agent_bot
if not exist logs mkdir logs
set PYTHONPATH=C:\Users\user\Desktop\agent_bot
:loop
echo [%date% %time%] Bot ishga tushmoqda... >> logs\bot.log
python main.py >> logs\bot.log 2>&1
echo [%date% %time%] Bot to'xtadi (kod: %errorlevel%), 10 soniyada qayta yonadi... >> logs\bot.log
timeout /t 10 /nobreak >nul
goto loop
