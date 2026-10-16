# Agent Bot — Windows avtostart + uyqu o'chirish (Administrator bilan ishga tushiring!)
# Ishlatish: PowerShell-ni "Run as Administrator" ochib:
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\scripts\install_autostart.ps1

$ErrorActionPreference = "Stop"
$AppDir = "C:\Users\user\Desktop\agent_bot"
$TaskName = "AgentBot"

# 1. Zaryadda uyqu rejimini o'chirish (bot o'lmasligi uchun)
powercfg -change standby-timeout-ac 0
powercfg -change hibernate-timeout-ac 0
Write-Host "Uyqu rejimi o'chirildi (zaryadda)."

# 2. Eski vazifa bo'lsa o'chirish
schtasks /delete /tn $TaskName /f 2>$null

# 3. Login'da avtostart (xato bo'lsa ham qayta urinish bilan)
$Action = New-ScheduledTaskAction -Execute "$AppDir\scripts\run_bot.bat" -WorkingDirectory $AppDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -DontStopOnIdleEnd
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "Agent Bot Telegram polling" | Out-Null
Write-Host "Avtostart o'rnatildi: $TaskName"
Write-Host "Tekshiruv: schtasks /query /tn $TaskName"
