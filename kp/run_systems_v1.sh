#!/bin/sh
# 蘂取線などの系統（特急 茂世路→択捉六甲は 789系1000番台の電車。特急 酪別→年萌だけはキハ283系相当：TILT=1 TRAIN=160。2026-11-05）（区間の並び、逆向きを含む）を、高さ指定なしと駅地平化の縦断で走らせる（2026-11-04）
set -e
cd "$(dirname "$0")"
for v in "" gs; do
  VMAX=130 TILT=0 TRAIN=170 python3 keito2.py sys_tokkyu_moyoro.json $v
  VMAX=110 TILT=0 TRAIN=120 python3 keito2.py sys_futsu_shibetoro.json $v
  VMAX=130 TILT=1 TRAIN=160 python3 keito2.py sys_tokkyu_rakki.json $v
  VMAX=110 TILT=0 TRAIN=120 python3 keito2.py sys_kaisoku_kuko.json $v
  VMAX=120 TILT=0 TRAIN=120 python3 keito2.py sys_futsu_tokite.json $v
  VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_sanroku.json $v
done
