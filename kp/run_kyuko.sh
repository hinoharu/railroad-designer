#!/bin/sh
# 急行 蘂取→丹根萌を、DD51形の重連の性能で走らせる（2026-11-05）
cd "$(dirname "$0")"
for v in "" gs; do P_KW=2260 MASS_T=379 FMAX_KN=330 TRAIN=140 VMAX=95 TILT=0 python3 keito2.py sys_kyuko.json $v > k_kyuko$v.log; head -1 k_kyuko$v.log; done
