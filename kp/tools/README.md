# セーブ・ダイヤの読み取り（kp/tools/）

国後島（2026-11-07）で、FreeTrain のセーブと OuDia 形式のダイヤから、区間・系統の入力表に要るものを読んだスクリプト。
択捉島で作業用フォルダに書いたもの（claude-workspace の `freetrain/scratchpad/tracks/`・`eki-radar/fiction/oud/`）を広げて写した。
前提：FreeTrain のリポジトリ（`hinoharu/freetrain_exav_alpha3_hino`）の `tools/SaveAnalyzer`（環境変数 `SAVEANALYZER`）と `plugins/`（`FT_PLUGINS`）。
セーブは `hinoharu/freetrain-saves` の zip を展開した `.ftgd3`。ダイヤはユーザーから受け取る。

| スクリプト | 入力 | 出力 |
|---|---|---|
| `save_rails.py セーブ 出力.json` | セーブ | 線路のマス（位置・型・向き・架線 `RailRoad._wire`）、駅、ホーム |
| `save_tracks.py rails.json 路線の駅の並び.json 出力.json` | 上の出力と {路線名: [駅…]} | 駅間ごとの複線・単線の判定と架線の割合（標準出力に要約） |
| `save_vehicles.py セーブ` | セーブ | 編成グループごとの車両のプラグイン・両数・速度・ダイヤの指定 |
| `save_groups.py セーブ` | セーブ | 編成グループごとの線路上の編成の数（状態）と controller の停車の設定のある駅 |
| `oud_parse.py ダイヤ.oud2` | ダイヤ | 駅の並び・種別・列車の数 |
| `oud_summary.py ダイヤ.oud2` | ダイヤ | 種別ごとの「起点→終点（停車駅）」と本数 |
| `match_systems.py セーブ ダイヤ.oud2` | 両方 | 編成グループ（線路上のもの）とダイヤの列車の対応（停車駅の重なり、Jaccard 係数） |

`oud_parse.py` は、最上位に余分な「.」がある generated のダイヤも読む。駅名の違い（安渡移矢港→安渡移矢岬など）は `match_systems.py` の `norm` で吸収する。
