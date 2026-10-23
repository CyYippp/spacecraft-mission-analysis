@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m spacecraft_mission_analysis.dashboard --config "examples\vanguard_run\config.json"
) else (
  py -3 -m spacecraft_mission_analysis.dashboard --config "examples\vanguard_run\config.json"
)
if errorlevel 1 pause
