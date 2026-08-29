$TOKEN = $env:GITHUB_TOKEN
if (-not $TOKEN) { Write-Output "ERROR: GITHUB_TOKEN not set"; exit 2 }
$REPO = "lm203688/roboparts"
$BATCH = 3
$MAXTRY = 15
$SLEEP = 6
$OUTER = 18
$REMOTE = "https://x-access-token:$TOKEN@github.com/$REPO.git"
Set-Location C:\Users\xing\Desktop\robopart

git remote remove gpf 2>$null
git remote add gpf $REMOTE

function Get-RemoteHead {
  for ($r = 1; $r -le 3; $r++) {
    try {
      $line = git ls-remote --heads gpf 2>$null | Where-Object { $_ -match 'refs/heads/main' } | Select-Object -First 1
      if ($line) { return ($line -split '\s+')[0] }
    } catch {}
    Start-Sleep -Seconds 4
  }
  return $null
}

$list = @(git rev-list --reverse HEAD)
$n = $list.Count
Write-Output "Local commits: $n | outer-loop attempts: $OUTER"

for ($outer = 1; $outer -le $OUTER; $outer++) {
  $remoteHead = Get-RemoteHead
  if (-not $remoteHead) { Write-Output "[outer $outer] 远端不可达，跳过本轮"; Start-Sleep -Seconds 20; continue }
  $resume = 0
  for ($k = 0; $k -lt $n; $k++) { if ($list[$k] -eq $remoteHead) { $resume = $k + 1; break } }
  if ($resume -ge $n) { Write-Output "[outer $outer] 远端已等于 HEAD，完成"; git remote remove gpf 2>$null; exit 0 }
  Write-Output "[outer $outer] 远端 HEAD=$($remoteHead.Substring(0,8)) 从 index $resume 续推"
  $i = $resume; $batchNo = 0; $done = $false
  while ($i -lt $n) {
    $end = [math]::Min($i + $BATCH, $n)
    $tip = $list[$end - 1]; $batchNo++
    $ok = $false
    for ($attempt = 1; $attempt -le $MAXTRY; $attempt++) {
      Write-Output "  batch#$batchNo commits $($i+1)-$end tip $($tip.Substring(0,8)) attempt $attempt"
      $out = git -c http.lowSpeedLimit=1 -c http.lowSpeedTime=300 push gpf "$tip`:refs/heads/main" --force 2>&1
      if ($LASTEXITCODE -eq 0) { $ok = $true; Write-Output "    OK"; break }
      Write-Output "    FAIL: $($out | Select-Object -Last 1)"
      Start-Sleep -Seconds $SLEEP
    }
    if (-not $ok) { Write-Output "  [outer $outer] 本批次网络失败，进入下一轮外层重试"; Start-Sleep -Seconds 15; break }
    $i = $end
  }
  if ($i -ge $n) { Write-Output "=== 全部批次完成 ==="; git ls-remote --heads gpf 2>&1 | Select-Object -First 1; git remote remove gpf 2>$null; Write-Output "DONE"; exit 0 }
}
Write-Output "=== 外层重试耗尽，远端停在最近成功批次（下次运行可续推）==="
git remote remove gpf 2>$null
exit 1
