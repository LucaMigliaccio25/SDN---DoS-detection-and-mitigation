#!/usr/bin/env bash
# Eseguire dall'host h1 nella CLI Mininet: h1 bash /PERCORSO/scripts/bitrate_var_headless.sh
set -euo pipefail
for rate in 4M 1M 6M; do
  echo "[h1] UDP -> h3, bitrate ${rate}, durata 20 s"
  iperf -c 10.0.0.3 -u -b "$rate" -t 20 -p 5001
  sleep 1
done
