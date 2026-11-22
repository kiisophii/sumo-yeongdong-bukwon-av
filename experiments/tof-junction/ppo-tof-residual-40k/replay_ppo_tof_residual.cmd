@echo off
setlocal
cd /d "%~dp0..\..\.." || exit /b 1
set "PYTHONUTF8=1"
set "MERGE_COOP=0"
set "MERGE_SPEEDMATCH=0"
set "ROUNDABOUT_VMAX=0"
set "LC_TRACK_SUMO=0"
set "EXEC_ACTION_BUFFER=0"
set "STEPS=40960"
if not "%~1"=="" set "STEPS=%~1"
set "TOF_RUN="
for /f "delims=" %%D in ('dir /b /ad /o-n "results\run_*_tof_ppo_tof_residual_40k" 2^>nul') do (
    if not defined TOF_RUN if exist "results\%%D\checkpoints\model_%STEPS%.pt" set "TOF_RUN=results\%%D"
)
if not defined TOF_RUN (
    echo No %STEPS%-step ToF acceleration residual PPO checkpoint found.
    exit /b 1
)
echo Evaluating "%TOF_RUN%\checkpoints\model_%STEPS%.pt" with PPO only.
py -u tools\trace_tof_junction_81.py --model "%TOF_RUN%\checkpoints\model_%STEPS%.pt" --seed 2353 --seed 2411 --seed 2401 --seed 2424
exit /b %ERRORLEVEL%
