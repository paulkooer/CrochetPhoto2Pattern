#!/bin/sh
# Round 3: rerun the round-1 acceptance scripts named in REPORT.md section 8 on the current checkout.
# Usage: sh r3_rerun_original_scripts.sh <repo root> <cardigan-open.json> > log
# Run from anywhere; the scripts themselves assert that `app` resolves to the repository.
repo=$1
input=$2
here=$(dirname "$0")
python="$repo/.venv/bin/python"

for sizes in "7.5 6.4285" "7.1 6.4285" "7.5 6.0714" "7.1 6.0714"; do
  echo "##### ribbing_start_direction.py, body and sleeve length in cm: $sizes"
  # shellcheck disable=SC2086
  "$python" "$here/ribbing_start_direction.py" "$input" $sizes 2>&1
  echo "exit=$?"
done
for script in cardigan_sweep.py; do
  echo "##### $script"
  "$python" "$here/$script" "$input" 2>&1
  echo "exit=$?"
done
for script in model_guarantee_probes.py doll_increase_columns.py doll_arithmetic.py; do
  echo "##### $script"
  "$python" "$here/$script" 2>&1
  echo "exit=$?"
done
