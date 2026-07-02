#!/usr/bin/env bash
# Secret scan — run BEFORE any push or before making the repo public.
# Checks the working tree AND the full git history for accidentally leaked
# API keys, GitHub tokens, bcrypt/basic-auth hashes, and ensures the secret
# files are gitignored + untracked. Exits non-zero if anything looks wrong,
# so it can be wired as a pre-push hook.
#
#   bash tools/secret_scan.sh
#
# Patterns are deliberately specific (real keys, not the substring "sk-") to
# avoid false positives on words like "task-" or placeholders like "sk-...".

set -u
cd "$(git rev-parse --show-toplevel)" || { echo "not a git repo"; exit 2; }

FAIL=0
note()  { printf '  %s\n' "$1"; }
bad()   { printf 'FAIL  %s\n' "$1"; FAIL=1; }
ok()    { printf 'OK    %s\n' "$1"; }

# Real secret signatures (NOT the bare "sk-" substring).
KEY='sk-[A-Za-z0-9]{20,}'                                   # Qwen / OpenAI key
PAT='ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'      # GitHub PAT
HASH='\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{20,}'                # bcrypt / caddy hash
COMBINED="($KEY|$PAT|$HASH)"

echo "== 1/4  Working tree (tracked + untracked, respecting .gitignore) =="
# --exclude-standard skips gitignored files (.env etc.) — they never get pushed.
HITS=$(git grep -nIE --untracked --exclude-standard "$COMBINED" -- ':!*.png' ':!*.jpg' ':!tools/secret_scan.sh' 2>/dev/null || true)
if [ -n "$HITS" ]; then bad "possible secret in the working tree:"; echo "$HITS"; else ok "no key/token/hash in the working tree"; fi

echo "== 2/4  Full git history (all branches) =="
for label in "API key:$KEY" "GitHub PAT:$PAT" "auth hash:$HASH"; do
  name=${label%%:*}; pat=${label#*:}
  H=$(git log --all --oneline -G "$pat" 2>/dev/null || true)
  if [ -n "$H" ]; then bad "$name pattern appears in history:"; echo "$H"; else ok "no $name ever committed"; fi
done

echo "== 3/4  Secret files must be gitignored AND untracked =="
for f in .env deploy/app.env deploy/caddy.env; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    bad "$f is TRACKED by git (must not be)"
  elif [ -f "$f" ] && ! git check-ignore -q "$f"; then
    bad "$f exists but is NOT gitignored"
  else
    ok "$f safe (ignored / not tracked)"
  fi
done

echo "== 4/4  .gitignore sanity =="
for e in ".env" "deploy/app.env" "deploy/caddy.env"; do
  if grep -qF "$e" .gitignore 2>/dev/null; then ok ".gitignore covers $e"; else bad ".gitignore is missing an entry for $e"; fi
done

echo
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: PASS — no secrets found. Safe to push."
else
  echo "RESULT: FAIL — review the findings above BEFORE pushing. Do not go public yet."
fi
exit "$FAIL"
