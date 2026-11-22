#!/bin/sh
# Round 3: the last verification pass, in one command.
# Usage: sh r3_finish.sh <repo root>      (writes logs/r3-finish-*.log beside the other logs)
repo=$1
here=$(dirname "$0")
logs="$here/../../logs"
python="$repo/.venv/bin/python"
cd "$repo" || exit 1

echo "== 1. round-1 acceptance scripts on this checkout"
sh "$here/r3_rerun_original_scripts.sh" "$repo" \
  "$repo/eval_outputs/fable52-system-audit-20261117/examples/inputs/cardigan-open.json" \
  > "$logs/r3-original-acceptance-scripts.log" 2>&1
grep -c "" "$logs/r3-original-acceptance-scripts.log"

echo "== 2. static checks"
{
  echo "### ruff"; "$repo/.venv/bin/ruff" check app tests scripts/ci_scope.py scripts/changelog_fragments.py \
    scripts/bind_release_evidence.py; echo "ruff exit=$?"
  echo "### mypy"; "$repo/.venv/bin/mypy" app tests | tail -1; echo "mypy exit=$?"
  echo "### changelog fragments"; "$python" scripts/changelog_fragments.py check; echo "changelog exit=$?"
} > "$logs/r3-finish-static.log" 2>&1
grep -E "exit=|Success|passed|valid|error" "$logs/r3-finish-static.log"

echo "== 3. whole suite with coverage, as CI runs it"
"$python" -m pytest -q -p no:cacheprovider --cov=app --cov-report=term --cov-fail-under=80 \
  > "$logs/r3-full-pytest-final.log" 2>&1
echo "pytest exit=$?" >> "$logs/r3-full-pytest-final.log"
tail -4 "$logs/r3-full-pytest-final.log"

echo "== 4. copy report and small evidence into docs/reviews"
"$python" "$here/r3_publish_to_docs.py" "$repo"
