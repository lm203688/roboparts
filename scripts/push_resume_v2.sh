#!/usr/bin/env bash
# Force-push lm203688/roboparts history in small batches with resume + retry.
# Token is taken ONLY from $GITHUB_TOKEN (env) and used via inline git -c
# url...insteadOf so it is NEVER written to .git/config or any file.
set +e
REPO="lm203688/roboparts"
TOKEN="$GITHUB_TOKEN"
BATCH=3
OUTER=25
MAXTRY=15
SLEEP=6
cd /c/Users/xing/Desktop/robopart || exit 3

mapfile -t list < <(git rev-list --reverse HEAD)
n=${#list[@]}
echo "Local commits: $n"

for ((outer=1; outer<=OUTER; outer++)); do
  remoteHead=""
  for ((r=1; r<=5; r++)); do
    remoteHead=$(git ls-remote --heads "https://x-access-token:$TOKEN@github.com/$REPO.git" 2>/dev/null | awk '/refs\/heads\/main/{print $1; exit}')
    [ -n "$remoteHead" ] && break
    sleep 5
  done
  if [ -z "$remoteHead" ]; then echo "[outer $outer] remote unreachable, skip"; sleep 20; continue; fi
  resume=0
  for ((k=0;k<n;k++)); do
    if [ "${list[$k]}" = "$remoteHead" ]; then resume=$((k+1)); break; fi
  done
  if [ "$resume" -ge "$n" ]; then echo "DONE: remote already at HEAD ($remoteHead)"; exit 0; fi
  echo "[outer $outer] remote=${remoteHead:0:8} resume from index $resume"
  i=$resume; batchNo=0
  while [ $i -lt $n ]; do
    end=$((i+BATCH)); [ $end -gt $n ] && end=$n
    tip=${list[$((end-1))]}
    batchNo=$((batchNo+1))
    ok=0
    for ((attempt=1; attempt<=MAXTRY; attempt++)); do
      echo "  batch#$batchNo commits $((i+1))-$end tip ${tip:0:8} attempt $attempt"
      out=$(git -c "url.https://x-access-token:$TOKEN@github.com/.insteadOf=https://github.com/" \
               -c http.lowSpeedLimit=1 -c http.lowSpeedTime=300 \
               push origin "$tip:refs/heads/main" --force 2>&1)
      rc=$?
      if [ $rc -eq 0 ]; then ok=1; echo "    OK"; break; fi
      echo "    FAIL: $(echo "$out" | tail -1)"
      sleep $SLEEP
    done
    if [ $ok -eq 0 ]; then echo "  [outer $outer] batch network fail, retry outer"; sleep 15; break; fi
    i=$end
  done
  if [ $i -ge $n ]; then
    echo "=== ALL BATCHES DONE ==="
    git ls-remote --heads "https://x-access-token:$TOKEN@github.com/$REPO.git" 2>&1 | head -1
    exit 0
  fi
done
echo "=== outer retries exhausted; resume on next run ==="
exit 1
