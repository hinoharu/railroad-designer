#!/bin/sh
# 蘂取線などの系統（特急 茂世路→択捉六甲は 789系1000番台の電車。特急 酪別→年萌だけはキハ283系相当：TILT=1 TRAIN=160。2026-11-05）（区間の並び、逆向きを含む）を、車両の性能の表（vehicles.json、2026-11-06）で、高さ指定なしと駅地平化の縦断で走らせる（2026-11-04）
set -e
cd "$(dirname "$0")"
for v in "" gs; do
  env $(python3 veh_env.py 789系1000番台 8) VMAX=130 TILT=0 TRAIN=170 python3 keito2.py sys_tokkyu_moyoro.json $v
  env $(python3 veh_env.py 719系 6) VMAX=110 TILT=0 TRAIN=120 python3 keito2.py sys_futsu_shibetoro.json $v
  env $(python3 veh_env.py キハ283系 8) VMAX=130 TILT=1 TRAIN=160 python3 keito2.py sys_tokkyu_rakki.json $v
  env $(python3 veh_env.py 719系 6) VMAX=110 TILT=0 TRAIN=120 python3 keito2.py sys_kaisoku_kuko.json $v
  env $(python3 veh_env.py 731系 6) VMAX=120 TILT=0 TRAIN=120 python3 keito2.py sys_futsu_tokite.json $v
  env $(python3 veh_env.py キハ120形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_sanroku.json $v
  env $(python3 veh_env.py キハ40形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_furu.json $v
  env $(python3 veh_env.py キハ40形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_atosa.json $v
  env $(python3 veh_env.py キハ40形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_noto.json $v
  env $(python3 veh_env.py キハ40形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_yorib.json $v
  env $(python3 veh_env.py キハ40形 4) VMAX=85 TILT=0 TRAIN=80 python3 keito2.py sys_futsu_otoshi.json $v
  env $(python3 veh_env.py キハ150形 3) VMAX=85 TILT=0 TRAIN=60 python3 keito2.py sys_futsu_moke.json $v
done
