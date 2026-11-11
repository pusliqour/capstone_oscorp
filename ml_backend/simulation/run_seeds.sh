#!/bin/zsh
# Repeat the whole benchmark on independent simulated worlds (post-protocol addition 6).
# Each seed: generate 1,000 stores -> alerts, forecasts, lost sales, transfers -> delete raw arrays.
set -e
cd "$(dirname "$0")"
PY=../../.venv/bin/python
TMP=${SEED_TMP:-output/seed_runs}
OUT=output/results/seeds
mkdir -p $OUT
for SEED in ${@:-1 2 3 4}; do
  D=$TMP/seed$SEED
  $PY generate.py --seed $SEED --out $D > $OUT/seed${SEED}_generate.log
  $PY evaluate_alerts.py --data $D --out $OUT/seed${SEED}_alerts.json > $OUT/seed${SEED}_alerts.log
  mkdir -p $OUT/seed${SEED}_fc
  $PY evaluate_forecasts.py --data $D --out $OUT/seed${SEED}_fc/forecasts.json > $OUT/seed${SEED}_forecasts.log 2>&1
  $PY evaluate_lost_sales.py --data $D --out $OUT/seed${SEED}_lost_sales.json > $OUT/seed${SEED}_lost_sales.log 2>&1
  $PY evaluate_transfers.py --data $D --stores all --out $OUT/seed${SEED}_transfers.json > $OUT/seed${SEED}_transfers.log
  cp $D/manifest.json $OUT/seed${SEED}_manifest.json
  rm -f $D/*.npy
  echo "seed $SEED done $(date +%T)"
done
