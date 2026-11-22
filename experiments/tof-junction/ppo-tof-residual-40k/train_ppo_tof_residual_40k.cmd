@echo off
setlocal
cd /d "%~dp0..\..\.." || exit /b 1

set "BASE_MODEL=results\run_20261122_064518_tof_adaptive_brake_target_4k\checkpoints\model_4096.pt"
if not exist "%BASE_MODEL%" (
    echo Missing pre-BC adaptive braking checkpoint: "%CD%\%BASE_MODEL%"
    exit /b 1
)

set "TEAM14_SCENARIO=museum"
set "TEAM14_TOF_OBS=1"
set "TEAM14_TOF_REAR_DENSITY=0"
set "TEAM14_TOF_LEAD_HOLD_S=0"
set "TEAM14_TOF_LEAD_GAP_WINDOW=0"
set "SUMO_USE_LIBSUMO=1"
set "SIM_REUSE="
set "ASSIST_PROB="
set "HARD_START_PROB=0"
set "STOP_SHAPING=0"
set "TEAM14_TOF_JUNCTION_YIELD=0"
set "JUNCTION_YIELD=0"
set "JUNCTION_ROW=0"
set "ROUTE_ASSIST_M=0"
set "ROUTE_SHIELD_M=0"
set "RED_STOP=0"
set "MERGE_SUMO=0"
set "MERGE_STOP=0"
set "ZIPPER_FOLLOW=0"
set "LC_REVERSE_COOLDOWN=0"
set "EXEC_ACTION_BUFFER=0"
set "MERGE_COOP=0"
set "MERGE_SPEEDMATCH=0"
set "ROUNDABOUT_VMAX=0"
set "LC_TRACK_SUMO=0"
set "PYTHONUTF8=1"

py -u train.py --init-model "%BASE_MODEL%" --ppo-accel-finetune --ppo-accel-residual --init-accel-scale 0.7 --timesteps 40960 --n-steps 2048 ^
    --lr 0.0001 --gamma 0.995 --seed 31 --ckpt-every 10240 ^
    --tof-route-lane-bonus 0.1 --tof-route-stall-weight 0 ^
    --tof-junction-yield-weight 0.4 --tof-junction-yield-preview ^
    --tof-junction-yield-reaction-s 2.0 --tof-junction-entry-penalty 2 ^
    --tof-junction-brake-weight 0.5 --tof-junction-brake-explore-std 0.8 ^
    --tof-junction-curriculum-share 0.75 --tof-junction-warmup-jitter-s 60 --tof-junction-curriculum-lane=-472043938#1_0 ^
    --tof-junction-north-south-vph 135 --tof-junction-safe-pass-bonus 1 ^
    --tof-junction-preentry-brake-bonus 0.5 --tof-junction-adaptive-brake-target --tof-junction-diagnostics --tag tof_ppo_tof_residual_40k
exit /b %ERRORLEVEL%
