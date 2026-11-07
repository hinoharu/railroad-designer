#!/bin/sh
# 使い方：sh runel.sh 種 重み D 名前（再起動のあとも同じコマンドで続きから）
cd "$(dirname "$0")"
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python3 fitel.py $1 $2 $3 $4 > sweep_$4.log 2>&1 && sh pipe.sh $4 >> sweep_$4.log 2>&1; echo "完了 $4" >> sweep_$4.log
