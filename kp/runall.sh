#!/bin/sh
# 使い方：sh runall.sh 重み D 名前（再起動のあとも同じコマンドで続きから）
cd "$(dirname "$0")"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 fitk.py $1 $2 $3 > sweep_$3.log 2>&1 && sh pipe.sh $3 >> sweep_$3.log 2>&1; echo "完了 $3" >> sweep_$3.log
