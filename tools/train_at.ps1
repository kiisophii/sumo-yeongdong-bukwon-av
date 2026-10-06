# 지정한 시각이 되면 train.py를 이 터미널에서 실행한다 (학습 로그가 화면에 그대로 보인다).
# 사용법 (PowerShell, course_repo 폴더에서):
#   & .\tools\train_at.ps1 -At 14:46 -Lr 1e-4 -Tag lr1e-4
#   & .\tools\train_at.ps1 -At 14:47 -Lr 3e-4 -Tag lr3e-4
# -At 를 비우면 바로 시작한다.
param(
    [string]$At = "",
    [string]$Lr = "1e-4",
    [string]$Tag = "",
    [int]$Timesteps = 200000
)

$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
Set-Location (Split-Path $PSScriptRoot -Parent)

if ($At -ne "") {
    $target = [datetime]::ParseExact($At, "HH:mm", $null)
    while ((Get-Date) -lt $target) {
        $left = [int]($target - (Get-Date)).TotalSeconds
        Write-Host -NoNewline ("`r{0} 에 학습 시작 (lr={1}) — {2}초 남음   " -f $At, $Lr, $left)
        Start-Sleep -Seconds 1
    }
    Write-Host ""
}

Write-Host ("[{0}] python train.py --lr {1} --timesteps {2} --tag {3}" -f (Get-Date -Format "HH:mm:ss"), $Lr, $Timesteps, $Tag)
python train.py --lr $Lr --timesteps $Timesteps --tag $Tag
