"""Write data/fiction_variants.json: the variants of the fictional lines, from the first try to the adopted one, with the conditions
they were computed under and their results, for the comparison on the test page src/test/align.html (2026-11-05, the user's request:
compare the results from the first to the last under the various conditions; even the absurd ones are worth keeping. Later the
variants that were not adopted move to a separate archive page, so this file and the comparison part of the page stand apart).

The variants are computed in claude-workspace eki-radar/fiction/kp_var/<id> by kp/variants.sh; the adopted ones are in kp itself.

  python3 scripts/fiction_variants.py KP_DIR   # KP_DIR: kp; the variants are read from KP_DIR/../kp_var
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KP = Path(sys.argv[1]).resolve(); VAR = KP.parent / "kp_var"
os.environ["FICTION_KP"] = str(KP)
sys.path.insert(0, str(ROOT / "scripts"))
import fiction_align as fa  # noqa: E402

FLAT = (-10.0, 12.0)   # 地平駅の範囲（地盤からの高さ、m。docs/fiction/align.md）
# the groups and their variants (ids as in kp/variants.sh); "dir": None is the adopted one, read from kp
GROUPS = [
    {"id": "sesibe", "name": "背蘂線（蘂取〜背祖曽）", "t": "sesibe", "route": "route_sesibe.json", "variants": [
        {"id": "S1", "dir": "S1", "name": "元の折れ線", "grade": "25‰", "plan": "元の折れ線", "note": "勾配で駅が地盤に届かない"},
        {"id": "S2", "dir": "S2", "name": "天幕→上去家だけ 15‰ で探した線", "grade": "15‰（単機の客車列車）", "plan": "元の折れ線、天幕→上去家だけ地形から探した線（15‰）",
         "note": "急行の全区間を 15‰ とした指定（誤タップ）で 1 駅間だけ探し、+16.6 km になって取りやめた"},
        {"id": "S3", "dir": "S3", "name": "駅の位置だけから引いた線（POC）", "grade": "25‰（重連）", "plan": "駅の位置だけ（元の折れ線を使わない）", "note": "将来の「駅の位置だけから線を描く」の試作"},
        {"id": "S4", "dir": "S4", "name": "元の折れ線に沿わせた線（25‰ で探す）", "grade": "25‰（重連）", "plan": "元の折れ線、収まらない 3 駅間だけ元の折れ線の帯の中で探した線", "note": "良宇仁が範囲外"},
        {"id": "S5", "dir": None, "name": "採用：元の折れ線に沿わせた線（蘂取→良宇仁は 24‰ で探す）", "grade": "25‰（重連）", "plan": "S4 と同じ。範囲外になった駅へ上る駅間だけ 1‰ 低く探す", "note": ""},
    ]},
    {"id": "moyoro", "name": "茂世路線（茂世路〜沼田）", "t": "moyoro", "route": "route_moyoro.json", "variants": [
        {"id": "M1", "dir": "M1", "name": "元の折れ線、急行も 35‰", "grade": "35‰（電化）", "plan": "元の折れ線", "note": ""},
        {"id": "M2", "dir": "M2", "name": "元の折れ線、急行の区間 15‰", "grade": "35‰、急行の区間（背祖曽〜沼田）15‰（単機）", "plan": "元の折れ線", "note": "誤タップの指定によるもの"},
        {"id": "M3", "dir": "M3", "name": "元の折れ線、急行の区間 25‰", "grade": "35‰、急行の区間 25‰（重連）", "plan": "元の折れ線", "note": ""},
        {"id": "M4", "dir": "M4", "name": "元の折れ線に沿わせた線 1 回目", "grade": "35‰、急行の区間 25‰（重連）", "plan": "元の折れ線、収まらない 2 駅間だけ元の折れ線の帯の中で探した線", "note": "去家がわずかに範囲外"},
        {"id": "M5", "dir": None, "name": "採用：元の折れ線に沿わせた線（去家→背祖曽は 34‰ で探す）", "grade": "35‰、急行の区間 25‰（重連）", "plan": "M4 と同じ。範囲外になった駅に接する駅間だけ 1‰ 低く探す", "note": ""},
    ]},
    {"id": "shibr", "name": "蘂取線（紗那〜沼田〜南留別）", "t": "shibr", "route": "route_shibetoro_r.json", "variants": [
        {"id": "R1", "dir": "R1", "name": "急行も 33‰", "grade": "33‰（電化）", "plan": "元の折れ線", "note": ""},
        {"id": "R2", "dir": "R2", "name": "急行の区間 15‰", "grade": "33‰、急行の区間（沼田〜南留別）15‰（単機）", "plan": "元の折れ線", "note": "誤タップの指定によるもの"},
        {"id": "R3", "dir": None, "name": "採用：急行の区間 25‰", "grade": "33‰、急行の区間 25‰（重連）", "plan": "元の折れ線", "note": ""},
    ]},
    # 単冠山麓線：単冠山口は両側の線が同じ側から入る駅（スイッチバック駅）。初めは通り抜けの 1 本（入里節〜長生内）として計算し、線形が駅の前後を近道した（N1・N2）。
    # 採用は単冠山口で 2 区間に分けたもので、ここでは北側（入里節〜単冠山口）と並べる。N1・N2 は範囲が違う（"t"・"route" で案ごとに指定）
    {"id": "sanroku", "name": "単冠山麓線 北側（入里節〜単冠山口）", "t": "sanroku_n", "route": "route_sanroku_n.json", "variants": [
        {"id": "N1", "dir": "N1", "t": "sanroku", "route": "route_sanroku.json", "name": "通り抜けの 1 本として、元の折れ線",
         "grade": "33.3‰（入里節〜特掟、電化）、25‰（非電化）", "plan": "元の折れ線（入里節〜長生内を 1 本として）",
         "note": "単冠山口で向きが 180° 変わる所を、線形の当てはめが近道し、駅が線形から離れた"},
        {"id": "N2", "dir": "N2", "t": "sanroku", "route": "route_sanroku.json", "name": "通り抜けの 1 本として、元の折れ線に沿わせた線",
         "grade": "33.3‰（入里節〜特掟、電化）、25‰（非電化）", "plan": "元の折れ線、収まらない 3 駅間だけ元の折れ線の帯の中で探した線（入里節〜長生内を 1 本として）",
         "note": "N1 と同じく単冠山口の前後 1.5 km を近道し、単冠山口が範囲外"},
        {"id": "N3", "dir": "N3", "name": "単冠山口で 2 区間に分け、元の折れ線に沿わせた線（120 km/h 前提）", "grade": "33.3‰（入里節〜特掟、電化）、25‰（非電化）",
         "plan": "元の折れ線、収まらない駅間（樺里信号場→単冠山口）だけ元の折れ線の帯の中で探した線。線形は最高速度 120 km/h の前提で当てはめた", "note": "南側（単冠山口〜長生内）は［すべての線形］で見る"},
        {"id": "N4", "dir": None, "name": "採用：N3 を 85 km/h 前提で当てはめ直した線", "grade": "33.3‰（入里節〜特掟、電化）、25‰（非電化）",
         "plan": "N3 と同じ経路。線形は最高速度 85 km/h の前提で当てはめた（芸備線・木次線のイメージ、ユーザーの指定）", "note": "南側（単冠山口〜長生内）は［すべての線形］で見る"},
    ]},
]
# 前の版（テスト版 256）の線形を案として残す（2026-11-06、ユーザーの指定：前の版も永続的に残す。背祖曽付近の二重のループが気に入っていた）。
# テスト版 257 で全区間を最新のプログラムの結果に統一し、10 区間が変わった。前の版の計算の結果は kp_var/V256（控えは claude-workspace の
# eki-radar/fiction/archive/v256）。上の群の採用の案は前の版に移し、最新の結果を新しい採用の案にする。群のない 7 区間は新しく群を作る
V256 = "前の版（テスト版 256）："
NEW = {"moyoro": ("M6", "最新のプログラムで作り直した線（去家→背祖曽 34‰、背祖曽→応仁萌 24‰ で探す）",
                  "M5 と同じ条件で、最新の地形からの探索（帯 300 m の追加、見つからないときの探し直し）で作り直した。背祖曽→応仁萌が短くなり背祖曽が範囲外になったので、その駅間も 1‰ 下げて 24‰ で探した", ""),
       "sesibe": ("S6", "S5 と同じ条件を、最新のプログラムで作り直した線", "S5 と同じ", "茂世路線の変更で、背祖曽の施工基面が変わった"),
       "sanroku": ("N5", "N4 と同じ条件を、最新のプログラムで作り直した線", "N4 と同じ", "蘂取線（択捉六甲〜類平）の変更で、入里節の分岐器の位置が変わった")}
for g in GROUPS:
    if g["id"] not in NEW: continue
    a = next(v for v in g["variants"] if v["dir"] is None)
    i, name, plan, note = NEW[g["id"]]
    g["variants"].append(dict(a, id=i, dir=None, name="採用：" + name, plan=plan, note=note))
    a.update(dir="V256", name=V256 + a["name"].replace("採用：", ""))
for gid, name, t, route, grade, cause in (
        ("shibw", "蘂取線（択捉六甲〜類平）", "shibw", "route_shibetoro_w.json", "33.3‰", "前の版は、分岐器での幹線の向きの測り方の修正（11-04）より前のプログラムの結果"),
        ("toshi", "茂世路線 冬知里支線（四谷〜塘路）", "toshi", "route_toshiruri.json", "25‰", "茂世路線の変更で、四谷の分岐器の位置と高さが変わった"),
        ("otamoi", "小田萌線（年萌〜新指臼）", "otamoi", "route_otamoi.json", "25‰", "蘂取線（択捉六甲〜類平）と茂世路線の変更で、両端の分岐器の位置と高さが変わった"),
        ("kuko", "択捉空港線（西単冠〜択捉空港〜植別）", "kuko", "route_kuko.json", "33.3‰（択捉空港〜植別 25‰）", "蘂取線（択捉六甲〜類平）の変更で、西単冠の分岐器の位置が変わった"),
        ("sanroku_s", "単冠山麓線 南側（単冠山口〜長生内）", "sanroku_s", "route_sanroku_s.json", "25‰", "北側の変更で、単冠山口の施工基面が変わった"),
        ("yorib", "寄別線（焼沼〜鬼門〜寄別）", "yorib", "route_yorib.json", "25‰", "小田萌線の変更で、焼沼の分岐器の位置と高さが変わった"),
        ("otoshi", "乙知志線（乙知志〜択捉原〜北乙）", "otoshi", "route_otoshi.json", "25‰", "茂世路線の変更で、乙知志の分岐器の位置と高さが変わった")):
    GROUPS.append({"id": gid, "name": name, "t": t, "route": route, "variants": [
        {"id": gid + "_256", "dir": "V256", "name": V256 + "それまでの線", "grade": grade, "plan": "元の折れ線", "note": ""},
        {"id": gid + "_257", "dir": None, "name": "採用：最新のプログラムで作り直した線", "grade": grade, "plan": "元の折れ線", "note": cause}]})
# 分岐器の規則の前（2026-11-08、ユーザーの指定：変更前の結果を比較できるように保持する）。kp_var/before_junction は、分岐器の位置の制限
# （停車場中心からの最小距離 JMIN・本線の勾配の上限 GJ・端の勾配を幹線に合わせる）と、構内の長さ（±110 m → TRAIN ÷ 2 ＋ 72 m）を入れる前の
# kp/ の写し（docs/junction.md）。古い手順の区間（ipg・sanpu）以外の全区間について、既にある群には案として足し、ない区間は新しく群を作る
# 同じく、面的な探索（devline3、2026-11-08）を入れる前の結果 kp_var/before_devline3（PR #2 のマージ時点の写し）も案として並べる。
# 「全区間に共通の、前の版」は (フォルダ, 案の名前の頭, 備考, 採用の案に足す備考) の表で増やす。古い順に並べる
SNAPSHOTS = [
    ("before_junction", "bj", "分岐器の規則の前（2026-11-08）：", "分岐器の位置の制限なし（作図の支線が駅の点から出ていると停車場中心が選ばれる）、構内は停車場中心 ±110 m", "分岐器の規則と構内の長さを入れて計算し直した"),
    ("before_devline3", "bd", "面的な探索の前（2026-11-08、PR #2）：", "地形からの探索は devline2（作図の線の帯の中を、縦断を固定して距離ごとの動的計画法で探す）", "面的な探索（devline3、A*）で地形から探し直した"),
]
sys.path.insert(0, str(KP / "tables")); import net  # noqa: E402
for SDIR, SUF, SNAME, SNOTE, ANOTE in SNAPSHOTS:
    if not (VAR / SDIR).exists(): continue
    by_t = {g["t"]: g for g in GROUPS}
    for s in net.SECTIONS:
        if s["method"] != "branch" or not (VAR / SDIR / f"fit_{s['id']}.json").exists(): continue
        g = by_t.get(s["id"])
        if g:
            a = next(v for v in g["variants"] if v["dir"] is None)
            g["variants"].insert(g["variants"].index(a), dict(a, id=s["id"] + "_" + SUF, dir=SDIR, name=SNAME + a["name"].replace("採用：", ""), note=SNOTE))
            a["note"] = ANOTE
        else:
            grade = f"{s['profile']['GCAP'] * 1000:g}‰"
            GROUPS.append({"id": s["id"], "name": s["name"], "t": s["id"], "route": s["route"]["file"], "variants": [
                {"id": s["id"] + "_" + SUF, "dir": SDIR, "name": SNAME + "それまでの線", "grade": grade, "plan": "元の折れ線（地形から探した駅間を含む）", "note": SNOTE},
                {"id": s["id"] + "_new", "dir": None, "name": "採用：いまの計算の結果", "grade": grade, "plan": "同上", "note": ANOTE}]})
SYSTEM_GROUP = {"id": "kyuko", "name": "急行 蘂取→丹根萌の性能", "variants": [
    {"id": "K1", "name": "キハ283系相当の性能（それまでの計算）", "car": "1 両 48 t に 365 kW", "len": 122},
    {"id": "K2", "name": "DD51形 単機＋客車 5 両", "car": "2,200 PS（レール 1,130 kW）、約 295 t", "len": 122},
    {"id": "K3", "name": "採用：DD51形 重連＋客車 5 両", "car": "2,200 PS×2（レール 2,260 kW）、約 379 t", "len": 140},
]}


def metrics(base, t, des_free, des_gs):
    out = {}
    df = json.load(open(base / des_free)); dg = json.load(open(base / des_gs))
    out["length_km"] = round(df["s"][-1] / 1000, 2)
    for k, d in (("free", df), ("gs", dg)):
        out["tunnel_" + k] = round(d["struct"].count("T") * 20 / 1000, 1); out["bridge_" + k] = round(d["struct"].count("B") * 20 / 1000, 1)
    bad = []
    for n, c in dg["stations"]:
        i = min(range(len(dg["s"])), key=lambda j: abs(dg["s"][j] - c)); g = dg["ground"][i]
        if g is None: continue
        h = dg["z"][i] - g
        if not (FLAT[0] <= h <= FLAT[1]): bad.append([n, round(h, 1)])
    out["out_gs"] = bad
    lst = json.load(open(base / f"curvelist_f{t}.json")); out["curves_lt300"] = sum(1 for c in lst if c["R"] < 300)
    fit = json.load(open(base / f"fit_{t}.json")); out["dev_max"] = round(max(abs(x) for x in fit["dev"]), 1)
    return out


def main():
    groups = []
    for g0 in GROUPS:
        vs = []
        for v in g0["variants"]:
            base = VAR / v["dir"] if v["dir"] else KP
            g = dict(g0, t=v.get("t", g0["t"]), route=v.get("route", g0["route"]))   # 案ごとに範囲が違うとき（単冠山麓線の N1・N2）
            if not (base / f"fit_{g['t']}.json").exists() or not (base / f"design_f{g['t']}.json").exists():
                print("skip（ない）", v["id"]); continue
            # only_gs の区間（国後島）は高さ指定なしの縦断を作らない：古い design_f<id>_free.json が残っていても使わず、駅地平化を両方に使う（2026-11-08）
            only_gs = g["t"] in net.SEC and net.SEC[g["t"]].get("profile", {}).get("only_gs")
            free_f = f"design_f{g['t']}_free.json" if (base / f"design_f{g['t']}_free.json").exists() and not only_gs else None
            orig = json.load(open(KP / g["route"]))["points"]
            sec = fa.section(g["id"], g["name"], g["t"], orig, design=free_f, alt=f"design_f{g['t']}.json", base=base)
            m = metrics(base, g["t"], free_f or f"design_f{g['t']}.json", f"design_f{g['t']}.json")
            note = v["note"]
            if (base / "infeasible").exists():   # the profile could not be solved under the grade (kp/variants.sh): kept as a result
                g_ = float((base / "infeasible").read_text().strip()) * 1000
                note += f"{'。' if note else ''}{g_:.0f}‰ では縦断が解けない（条件をすべて満たす高さがない）。表示の縦断は 25‰ で計算したもの"
            vs.append({k: v[k] for k in ("id", "name", "grade", "plan")} | {"note": note, "adopted": v["dir"] is None, "snapshot": v["dir"] if any(v["dir"] == x[0] for x in SNAPSHOTS) else None, "metrics": m, "section": sec})
            print(v["id"], m["length_km"], "km", "範囲外", m["out_gs"])
        groups.append({"id": g0["id"], "name": g0["name"], "kind": "section", "variants": vs})
    # the express with three performances (kp_var/K1..K3: keito2 files on the adopted alignments)
    NET = json.load(open(KP / "network.json")); ny = next(y for y in NET["systems"] if y["id"] == "kyuko")
    sec_ids = {"ipg": 0, "sanpu": 1, "shibw": 2, "shibr": 3, "moyoro": 4, "rakki": 5, "toshi": 6, "otamoi": 7, "sesibe": 8, "tanne": 9}
    vs = []
    for v in SYSTEM_GROUP["variants"]:
        d = VAR / v["id"]
        if not (d / "keito2_急行蘂取丹根萌.json").exists(): print("skip（ない）", v["id"]); continue
        k = json.load(open(d / "keito2_急行蘂取丹根萌.json")); kg = json.load(open(d / "keito2_急行蘂取丹根萌_gs.json"))
        r = lambda a: [round(q) for q in a]
        y = {"name": ny["name"], "car": v["car"], "path": [[sec_ids[s], a, b] for s, a, b in k["path"]], "dx": 10, "lim": r(k["lim"]), "v": r(k["v"]), "zone": r(k["zone"]),
             "run_min": round(k["run_min"], 1), "stations": [[n, round(c), 1 if n in k["stops"] else 0] for n, c in k["stations"]],
             "alt": {"lim": r(kg["lim"]), "v": r(kg["v"]), "zone": r(kg["zone"]), "run_min": round(kg["run_min"], 1)}}
        y["t"] = fa.elapsed(y["v"])[::10]; y["tdx"] = 100; y["alt"]["t"] = fa.elapsed(y["alt"]["v"])[::10]
        y["train"] = {"type": v["name"].replace("採用：", ""), "tilt": False, "cars": 7 if v["len"] == 140 else 6, "length": v["len"], "vmax": 95}
        # the speed on the steep parts: the lowest and the mean speed where the grade is 20 per mille or more (the gs profile)
        import numpy as np
        x = np.array(kg["x"]); vv = np.array(kg["v"]); zz = np.interp(x, kg["s"], kg["z"]); gr = np.gradient(zz, x) * 1000
        m = np.abs(gr) >= 20
        vs.append({"id": v["id"], "name": v["name"], "grade": "—", "plan": "—", "note": v["car"], "adopted": v["name"].startswith("採用"),
                   "metrics": {"run_min": y["run_min"], "run_min_gs": y["alt"]["run_min"], "steep_km": round(m.sum() * 10 / 1000, 1),
                               "steep_vmin": round(float(vv[m & (gr > 0)].min()), 0) if (m & (gr > 0)).any() else None,
                               "steep_vmean_up": round(float(vv[m & (gr > 0)].mean()), 0) if (m & (gr > 0)).any() else None},
                   "system": y})
        print(v["id"], y["run_min"], "分", vs[-1]["metrics"])
    groups.append({"id": "kyuko", "name": SYSTEM_GROUP["name"], "kind": "system", "variants": vs})
    out = {"source": "架空路線の案（claude-workspace eki-radar/fiction/kp_var と kp）", "license": "— （架空。テスト版と手元のビルドだけ）",
           "note": "案の比較（2026-11-05）。将来、採用した線形以外は別のページ（アーカイブ）に移す", "flat_range": FLAT, "groups": groups,
           # 全区間に共通の前の版（地図に重ねて今の結果と比べる。2026-11-08、ユーザーの指定）
           "snapshots": [{"id": d, "name": n.rstrip("：")} for d, _, n, _, _ in SNAPSHOTS if (VAR / d).exists()]}
    p = ROOT / "data" / "fiction_variants.json"
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(p, round(p.stat().st_size / 1024), "KB")


if __name__ == "__main__":
    main()
