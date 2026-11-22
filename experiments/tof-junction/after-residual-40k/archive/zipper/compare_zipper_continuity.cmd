@echo off
setlocal
cd /d "%USERPROFILE%\sumo-tof-junction-reward" || exit /b 1
set "MODEL=results\run_20261122_143625_tof_ppo_tof_residual_40k\checkpoints\model_40960.pt"
if not exist "%MODEL%" (
    echo Missing checkpoint: "%MODEL%"
    exit /b 1
)
set "PATCH=%~dp0tof_zipper_continuity.patch"
git apply --check "%PATCH%" >nul 2>&1
if errorlevel 1 (
    git apply --reverse --check "%PATCH%"
    if errorlevel 1 exit /b 1
) else (
    git apply "%PATCH%" || exit /b 1
)
set "PYTHONUTF8=1"
set "MERGE_COOP=0"
set "MERGE_SPEEDMATCH=0"
set "ROUNDABOUT_VMAX=0"
set "LC_TRACK_SUMO=0"
set "EXEC_ACTION_BUFFER=0"
echo === Original observation ===
set "TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY=0"
py -u tools\trace_tof_junction_81.py --model "%MODEL%" --seed 2336 --seed 2380 --seed 2329 || exit /b 1
echo === ToF conflict detection inside zipper merges ===
set "TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY=1"
py -u tools\trace_tof_junction_81.py --model "%MODEL%" --seed 2336 --seed 2380 --seed 2329
exit /b %ERRORLEVEL%
