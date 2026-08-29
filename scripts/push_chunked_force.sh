#!/usr/bin/env bash
# 分块强推：把线性历史按每 BATCH 个提交一批推到远端 main，
# 每批只传新增对象（小包），带重试，规避 api.github.com 大包 ECONNRESET。
set -u
TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$TOKEN" ]; then echo "ERROR: GITHUB_TOKEN 未设置"; exit 2; fi
OWNER_REPO="lm203688/roboparts"
BATCH=3
MAXTRY=6
SLEEP=4

# 内联 credential helper：用令牌作密码
CRED_HELPER="!f() { echo username=roboparts; echo password=$TOKEN; }; f"

cd "$(git rev-parse --show-toplevel)"

# 临时 remote
git remote remove gpf >/dev/null 2>&1 || true
git remote add gpf "https://github.com/$OWNER_REPO.git"

commits=($(git rev-list --reverse HEAD))   # 根在前，旧->新
n=${#commits[@]}
echo "总提交 $n，批大小 $BATCH"
i=0
batch_no=0
while [ $i -lt $n ]; do
  end=$((i+BATCH))
  if [ $end -gt $n ]; then end=$n; fi
  tip="${commits[$((end-1))]}"
  batch_no=$((batch_no+1))
  ok=0
  for attempt in $(seq 1 $MAXTRY); do
    echo "=== batch#$batch_no 提交 $[i+1]-$end (tip ${tip:0:8}) attempt $attempt ==="
    out=$(GIT_TERMINAL_PROMPT=0 git -c "credential.helper=$CRED_HELPER" \
      -c http.lowSpeedLimit=1 -c http.lowSpeedTime=300 \
      push gpf "$tip:refs/heads/main" --force 2>&1)
    rc=$?
    if [ $rc -eq 0 ]; then ok=1; echo "  OK"; break; fi
    echo "  FAIL(rc=$rc): $(echo "$out" | tail -2 | tr '\n' ' ')"
    sleep $SLEEP
  done
  if [ $ok -ne 1 ]; then echo "FAILED at batch#$batch_no (tip ${tip:0:8})"; git remote remove gpf >/dev/null 2>&1 || true; exit 1; fi
  i=$end
done

echo "=== 全部批次完成，校验远端 HEAD ==="
git -c "credential.helper=$CRED_HELPER" ls-remote --heads gpf 2>&1 | head
git remote remove gpf >/dev/null 2>&1 || true
echo "DONE"
