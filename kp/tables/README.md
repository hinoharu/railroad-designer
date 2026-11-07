# 入力表（人が決める値の正本）

2026-11-06、⑤プログラム化の段 1。`build.py` がこの表を読み、経路から系統の走行までを計算する（段 2）。
初版は `gen_once.py` が、それまでのファイルとつなぎのスクリプト（chain_*.sh・rerun_*.sh）から作った（一度だけ使う。以後はこの表を直す）。
`net.py` は表を読む共通の部品で、`build.py` と `keito2.py`（区間の縦断のファイル名 DESIGN と線の順位 RANK）が使う。

## sections.json（区間の表。1 区間 1 行）
| 項目 | 内容 |
|---|---|
| id・name・rank・grade・parents | network.json と同じ（線の順位、線路の等級、上位の線とつながる所の説明） |
| island | 経路を探す島（`path.route` に渡す） |
| method | `branch`：build.py が計算する。`legacy`：古い手順のまま（特急の経路 ipg、散布線 sanpu）。build.py は計算せず、縦断のファイルの中身だけを下位の区間の判定に使う |
| route.stops | 駅の並び（つながる区間の駅から先へ）。経路は作図の線をこの順に最短でつないで作る |
| route.file | 経路のファイル。あれば使い、`--remake-route` のときだけ作り直す |
| route.turnback | 始点の駅の先の折り返し（スイッチバック駅の行き止まり）を除くか |
| route.hybrid | 地形から探して経路を作り直す（devline_hybrid.py の GDEF：既定の勾配の上限、GMAP：駅間ごとの上限、PREFIX） |
| fit.trunk | 線形の当てはめ（ipfit_branch.py）の既定の幹線 |
| fit.ends | 端ごとの接続：`""` は既定の幹線、区間 id はその区間につながる。書かない端は、どの線にもつながらない |
| fit.free | どの線にもつながらない区間（スイッチバック駅で分けた後ろの区間など） |
| run | 線形の前提の最高速度 VMAX（km/h）、振子 TILT（0・1）、列車の長さ TRAIN（m） |
| profile.GCAP | 勾配の上限（0.025＝25‰） |
| profile.KYAKU25_ADD | 上限を 25‰ にする駅間（例：空港の前後） |
| profile.double | 複線の区間（駅の組） |
| profile.stations | 駅の高さの規則に対する例外。`free`（高さ指定なし）・`gs`（駅地平化）ごとに、駅名 → `[下, 上]`（地盤からの m）・`地平`・`指定なし` |
| profile.start_z_from | 始点の施工基面を、この区間の終点に合わせる（スイッチバック駅で分けたとき） |
| src | 値を読み取ったスクリプト |

駅の高さの規則（build.py の make_spec）：駅地平化の側は、経路の全駅を地平（−2〜+2 m）にする。ただし、上位の線につながる端の駅と、
`start_z_from` の始点の駅は除く。端の施工基面は、上位の線の縦断の、分岐器の位置の高さに合わせる。

## systems.json（系統の表。1 系統 1 行）
| 項目 | 内容 |
|---|---|
| id・name・sections | network.json と同じ |
| car_type・cars | 車両の表 vehicles.json の名前と両数（veh_env.py で性能にする） |
| perf | 車両の表にない車両の性能の直接指定（P_KW・MASS_T・FMAX_KN） |
| VMAX・TILT・TRAIN | 最高速度・振子・列車の長さ |
| sys_name・pieces・stops・note | 系統の経路（keito2.py の形）と停車駅。build.py が sys_<id>.json に書き出す |
| src | 値を読み取ったスクリプト |

古い手順の系統（特急 tokkyu は ipg の run.py、散布線の普通 futsu_sanpu は keito.py）は計算しない。

## 気づいた点（段 3 で規則にするときに扱う）
- スイッチバック駅の駅地平化の扱いが 2 か所でそろっていない：単冠山口（sanroku_s の始点）は `地平` を指定、散布泊（atosa_e2 の始点）は指定なし。
- 急行の車両（DD51 形重連＋客車）は車両の表にない。
