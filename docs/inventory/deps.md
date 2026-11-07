# 駅レーダーサイトと架空路線の線形づくりの依存（2026-11-06 調べ）

分類：(a) 本体の地図の架空路線の表示（駅レーダーサイトに残る）／(b) 線形づくりの確認用（分けたら移る）／(c) 両方が使う共通の部品。
依存の向き：「A → B」は A が B を読む・使う。パスの前置き：dev = /home/user/eki-radar-dev、kp = scratchpad/kp（控え cw = /tmp/cw/eki-radar/fiction/kp）。

## 1. eki-radar-dev の中の架空路線にかかわるもの

| ファイル・関数・データ | 分類 | 依存の向き | 根拠 |
|---|---|---|---|
| `src/index.template.html` の `fic`・`loadFiction`・`ficOn`・`applyFiction`・`fic.hitAt`・`selectFic`・`lcExRoutes` の架空の行・`#fictionRow`（［架空路線を表示（試験）］） | (a) | 本体 → `data/fiction.json` | dev/src/index.template.html:1193, 1524, 1548-1564, 3372, 3980-3992, 4063-4079, 4807, 4857-4868, 4917 |
| `data/fiction.json`（61 KB。路線・駅・線形） | (a)。ただし (b) の線形づくりも入力にする（→ (c) 寄り） | 本体 ← `scripts/fiction.py`。kp → これ | dev/data/sources.json:95、kp の 12 か所（2.参照） |
| `scripts/fiction.py`（405 行。GeoJSON から fiction.json を作る） | (a) の元データ作り。`metres`・`project` を kp が import するので (c) | → `data/fiction_src/`（入力）、→ `data/fiction.json`（出力） | dev/scripts/fiction.py:20-22, 35, 39 |
| `data/fiction_src/`（GeoJSON 4 本、tsv 5 本） | (a) の入力 | `fiction.py` が読む | dev/scripts/fiction.py:254-275、dev/data/sources.json:98 |
| `scripts/fiction_align.py`（219 行） | (b) | dev → kp を読む（3.参照） | dev/scripts/fiction_align.py:12-19, 35-67, 129-213 |
| `scripts/fiction_variants.py`（135 行） | (b) | dev → kp と kp_var を読み、`fiction_align` を import | dev/scripts/fiction_variants.py:14-17, 87-91, 103 |
| `data/fiction_align.json`（5.76 MB） | (b) | `fiction_align.py` が出力 → `align.html` が読む | dev/data/sources.json:96、dev/src/test/align.html:159 |
| `data/fiction_variants.json`（4.47 MB） | (b) | `fiction_variants.py` が出力 → `align.html` が読む | dev/data/sources.json:97、dev/src/test/align.html:184 |
| `src/test/align.html`（821 行。地図と縦断面図） | (b) | → `../fiction_align.json`・`../fiction_variants.json`（平文、なければ `.enc` を復号）。Leaflet は cdnjs | dev/src/test/align.html:140, 149-186 |
| `src/test/pip.html`（小窓の位置情報の確認） | 架空路線とは無関係（grep に出たのは `align` の語のみ） | — | 「どの語が出たか」の確認のみ。不明点なし |
| `scripts/build.py`：`data/sources.json` の `how: copy` と `stages` に従って dist に写す。`sealed: ["stg"]` なら `STG_SEAL_PASS` で暗号化（`.enc`）。`src/test/*.html` を `stage != "prd"` のとき `dist/test/` に出力 | (c)（仕組みは汎用で、架空路線の名前は書かれていない） | build.py → sources.json の台帳 | dev/scripts/build.py:174-175, 218-253, 282-300 |
| `scripts/publish.js`：台帳の `copy` かつその段階のものだけ送る。`.enc` は stg だけ。`dist/test` も扱う | (c) | publish.js → sources.json | dev/scripts/publish.js:187-197 |
| `data/sources.json`：`user_fiction` の出典、`fiction.json`／`fiction_align.json`／`fiction_variants.json`／`fiction_src` の台帳項目 | (c) | build.py・publish.js・check_data.js がこれを読む | dev/data/sources.json:55-61, 95-98 |
| `tests/check_data.js`：`user_fiction` を持つファイルは prd に出さない・暗号化の段階にも prd を含めない | (c) | tests → sources.json | dev/tests/check_data.js:61-62 |
| `src/sw.js`：`.enc` は network-first。`fiction*.json` の名前の個別の記述は無い | (c) | sw.js は架空路線を知らない | dev/src/sw.js:68（`extra|osm_*` と `.enc` のみ。`fiction` の grep は 0 件） |
| 暗号化（seal） | (c) | `build.py`（`STG_SEAL_PASS`）が暗号化。`align.html` は自前で AES-GCM / PBKDF2 の復号を持つ（本体の `seal`・`dataUsable` と別実装） | dev/scripts/build.py:225-235、dev/src/test/align.html:149-176、本体の `seal` は index.template.html の最上位 script（shared_survey.md の 0 の表） |
| `tests/verify.js`・`check_html.js`・`check_publish.js` | 架空路線の記述なし | — | `grep fiction tests/*.js` は check_data.js のみ |
| 仕様 `docs/spec/drawing.md` の「架空路線」（30〜208 行の節。線形づくりの規則・結果まで含む。2026-11-06 に、線形づくりの部分は `docs/fiction/align.md`・`thresholds.md`・`history.md` へ移し、drawing.md には地図への表示の部分だけを残した）、`thresholds.md`（24-25, 93）、`docs/fiction/README.md`、`HANDOFF.md`（9, 10 行） | 文書。本体の表示は (a)、線形の設計は (b) が混在 | 文書の中で (a) と (b) が同じ節にある | dev/docs/spec/drawing.md:30-208 |
| `scripts/shots/*`・`src/guide/*`・`CLAUDE.md` の grep 該当 | 無関係（`align-items`、「架空の記録」の画像の説明など） | — | 内容の語は fiction/架空路線ではない（例：shots/README.md:27 は「架空の取得状況」） |

補足：`scripts/n05_*.py`・`local/` の grep 該当は `align` の語（国土数値情報の位置合わせ）で、架空路線とは無関係。

## 2. kp → eki-radar-dev の依存

kp は 1205 ファイル。次の 2 種類が確認できた。

| kp のファイル | 何を使うか | 根拠 |
|---|---|---|
| `devline_hybrid.py:8-9`、`devline_hybrid_sesibe.py:8-9`、`make_devroute.py:5-6`、`path.py:3-4` | `sys.path.insert(0,'/home/user/eki-radar-dev/scripts')` の後 `from fiction import metres, project` | kp の各行 |
| `fit2route.py:4-10`、`ground.py:5-6`、`reroute.py:4-5`、`variants.sh:28`、`fit2route_v1.py:4` | 同上（`metres` のみ） | 同上 |
| `fit2route.py:6`、`reroute.py:7`、`path.py:5`、`prep.py:6`、`ipfit_all.py:269`、`ipfit_all_v5.py:264`、`ipfit_branch.py:219`、`ipfit_branch_v1〜v4.py`、`fit2route_v1.py:6` | `/home/user/eki-radar-dev/data/fiction.json`（駅の座標、路線）を絶対パスで読む。12 か所 | `grep` の件数 12 |
| `register6.py:3, 64` | `/home/user/eki-radar-dev/scripts/fiction_align.py` の本文を読み書きして、ページの区間と系統の一覧に追記する | register6.py:64 |
| 合計 | 絶対パスの `eki-radar-dev/scripts` が 11 か所、`data/fiction.json` が 12 か所、`fiction_align.py` が 2 か所 | grep の集計 |

kp が dev から使う関数は `fiction.metres`（2 点間の距離 m）と `fiction.project`（点を線分に射影）の 2 つだけ（上の import 行）。`fiction.json` の形は `stations`（`x[0]` が名前、`x[3]/1e5`・`x[2]/1e5` が座標）を kp が直接解釈している（ipfit_all.py:269 付近）。kp が dev の他のデータ（lines.json など）を読むかは、今回の grep の範囲では見つからず、不明（未確認）。

## 3. eki-radar-dev → kp の依存

| dev のファイル | 何を kp から読むか | 根拠 |
|---|---|---|
| `scripts/fiction_align.py` | 引数または環境変数 `FICTION_KP` で KP を指定。`sys.path` に KP を入れて `from run import simulate`（走行時間のモデル。numpy・scipy を使う）。`fit_*.json`・`route_f*.json`・`design_f*.json`・`curvelist_f*.json`・`curves_f*.json`・`network.json`・`route_*.json`・`keito*_*.json` などを読む | dev/scripts/fiction_align.py:16-19, 35-38, 62-67, 129-192 |
| `scripts/fiction_variants.py` | KP と、その隣の `kp_var`（`KP.parent / "kp_var"`）を読む。`network.json`、`route`。`fiction_align` を import して関数を再利用 | dev/scripts/fiction_variants.py:14-17, 87-91, 103 |
| `data/sources.json` の記述 | 「claude-workspace eki-radar/fiction/kp の設計の結果」と出典に書く（文章だけで、機械的な読み込みではない） | dev/data/sources.json:96-97 |

結果：kp ⇔ dev が、**双方向**に絶対パス・相対パスで結ばれている（kp が `fiction.py`・`fiction.json`・`fiction_align.py` を使い、dev の `fiction_align.py` が kp の中間ファイルと `run.py` を使う）。

## 4. claude-workspace（/tmp/cw）eki-radar/ の構成（架空路線にかかわる所）

| パス | 中身（確認できた範囲） |
|---|---|
| `/tmp/cw/eki-radar/fiction/kp`（1117 ファイル） | 計算の本体の控え。scratchpad の kp（1205 ファイル）とは数が違う（差の理由は不明） |
| `fiction/kp_var`（K1〜K3、M1、M2 ほか） | 案の比較の結果。`fiction_variants.py` が読む |
| `fiction/kp_moyoro_v1`、`kp_sesibe_draw` | 作業の途中の別版 |
| `fiction/oud`（`lines_cat.py`、`parse.py`、`sections.py`、`speed2.py`、`trains.py`、`verify_ms.py`） | ダイヤ（OuDia の a.oud2）の解析 |
| `fiction/veh`、`fiction/trace`（comic_*.png）、`fiction/ui`、`fiction/app2`（karishi.png など）、`fiction/backup_align_232`、`dangle.py`、`ends.py`、`guess.tsv`、`guess_pick.json`、`lines_new6.json`、`tracks_new6.json`、`view.py`、`shot.js`、各地の png | 車両、手がかり画像、画面の試作、補助スクリプト（個別の中身は未確認） |
| `shared/shared_survey.md`、`shared/gray_review.md` | 共通部品の調査（5.） |
| 同階層の `n05`、`osm_pipeline`、`review`、`artifact-db`、`notes`、`uploads` ほか | 架空路線とは別の作業 |

## 5. 共通化の状況

- 調査の文書：`shared_survey.md`（index.template.html 5441 行の部品を A 切り出し可／B 書き換え要／C 専用に分類、調査日 2026-11-02）と `gray_review.md`（B の 16 部品と StickyCanvas を審査）。
- **「2026-11-03 に決めた方針」そのものの記録は、この 2 文書にも HANDOFF 2 本にも見つからなかった**（`11-03` の grep は 0 件）。審査の結論（下）だけが記録としてある。日付と決定の経緯は不明。
- 審査の結論（gray_review.md の一覧表）：入れるべき＝StickyCanvas(A1)・`store`(B1、`ns` を必須にする)・鉄道の線の描画の一部(B5)・中心にする領域(B7、最優先)・縮尺の表示(B9)。今は早い＝B2・B3・B6・B11・B16・路線図の縦描画。入れるべきでない＝B4・B8・B10・B12〜B15。共通の注意：Leaflet 1.9.4 固定を契約に含める、B7・B2・B9 は `area()` を土台にする、`store` の全走査を `keys()` に置き換える。
- 実際の進み具合：**未着手**。dev に共通ライブラリのフォルダ・ファイルは無い（`scripts/` と `src/` を ls して、shared／common／lib に当たるものは 0。`src/vendor/` は delaunator のみ）。`index.template.html` の 1 バイトも変更されていないことを示す記録も無い。今回の依存調べでは、確認できた共有は kp が `fiction.py` の 2 関数を import しているだけ。
- なお、この文書の対象は「地図の UI の部品」（新アプリの地図に使う）であり、「線形づくりの計算」（`fiction.py` の `metres`・`project` など）の共通化は含まない。

## 6. 分けるとしたら（案）

| 区分 | 内容 |
|---|---|
| 駅レーダーサイトに残す | (a) 本体の表示（index.template.html の fic 周辺）、`fiction.json` を読む処理。`data/fiction.json` と元データ `fiction_src/`・`fiction.py` は、本体が読むので当面残す（案 A）。台帳・build・publish・check_data・sw.js の汎用の仕組みは変更なしで残す |
| 線形づくり側（新しいリポジトリ）へ移す | kp 一式（1117〜1205 ファイル）、`kp_var`、`oud`、`veh`、`fiction_align.py`、`fiction_variants.py`、`align.html`（確認用ページ）、`fiction_align.json`・`fiction_variants.json`（10 MB 超）、docs/spec/drawing.md の線形づくりの節（60 行目以降の約 150 行）、thresholds.md の kp の節 |
| 共通にする | ① `metres`・`project`・座標の符号化（`fiction.py` の一部）を小さな Python モジュールにする（kp が絶対パスで import している唯一の関数）。② `fiction.json` の形式を「契約」として文書化する（kp が `stations` の配列の添字で直読みしている）。③ gray_review.md の UI 部品（StickyCanvas・store・centerArea など）は、地図を使う新アプリが出てから。今回は線形づくりとは別の話 |

ユーザーの判断が要る所：
1. `fiction.json` と元データ（`fiction_src`、`fiction.py`）の持ち主。本体が読み、kp も読む。案 A：dev に残して新リポジトリが dev を参照する（今と同じ依存の向きが残る）／案 B：新リポジトリに移し、dev は成果の `fiction.json` を受け取る（本体のビルドが新リポジトリの成果に依存する）／案 C：`metres`・`project` と `fiction.json` を小さな共通パッケージに切り出す。
2. 双方向の結びつきを一方向にするか。例えば、新リポジトリの出力（`fiction.json`／`fiction_align.json`）を dev に取り込むだけにして、dev から kp を読む処理（fiction_align.py）は新リポジトリに移す、など。
3. `align.html`・`fiction_align.json`・`fiction_variants.json` を、どちらのビルド（テスト版）で公開するか。暗号化と台帳（sources.json）の仕組みは dev 側にあるので、新リポジトリに移すと、その複製か参照が要る。
4. 共有ホスト（hinoharu.github.io）での localStorage・Cache の衝突の対策（gray_review.md の冒頭）を、先に決めるか。
5. 2026-11-03 の方針の中身（日付が記録に無いため、どの結論を指すかの確認）。
   → 照合の結果（11-06、Claude）：記録はある。HANDOFF の「決まったこと（11-03）」に要約、細部は HANDOFF の版 a8973f7（11-03）の 11 行目（共通ライブラリの候補 `StickyCanvas`・`store`・`stroke`・中心の領域・縮尺など）。その後 HANDOFF を短くしたときに細部が削られた（docs/radar_restore.md）。

## 7. 不明・未確認
- 「2026-11-03 の方針」の記録の所在。
- cw の kp（1117）と scratchpad の kp（1205）の差分の内容。
- kp が dev の `fiction.json` 以外のデータ（lines.json、標高 DEM など）を読むか。DEM の取得元は未確認。
- `src/sw.js` が `test/align.html` や `fiction*.json` を個別に扱うか：`fiction` の grep は 0 件。ただし `.enc` と `test/` の扱いは未確認。
