#!/bin/sh
# 新しい制限速度の式で、自由曲線 → 線形要素 → 縦断・走行を計算する。区間ごとに途中保存するので、同じコマンドで続きから再開できる
# 使い方：sh rerun.sh D（30）
cd "$(dirname "$0")"
D=$1; K=n1e5d$D; E=m1e5d$D
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
[ -s fit_$K.json ] || python3 fitk.py 100000 $D $K > sweep_$K.log 2>&1
[ -s design_f$K.json ] || sh pipe3.sh $K >> sweep_$K.log 2>&1
[ -s fit_$E.json ] || python3 fitel.py $K 100000 $D $E > sweep_$E.log 2>&1
sh pipe3.sh $E >> sweep_$E.log 2>&1
echo "完了 $D" >> sweep_$E.log
