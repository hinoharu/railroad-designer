"""Write data/fiction_align.json: the designed network of the fictional Etorofu lines (sections: the trunk and its branches)
and the systems running on it (the express 蘂取→兵至平, the local 大岬→紗那), for
the test page src/test/align.html (test site and local builds only; sealed on the test site like data/fiction.json).

The alignments are made in hinoharu/claude-workspace eki-radar/fiction/kp (path.py: the route along the drawn lines;
ground.py: GSI elevation; fitk.py: the plan as curvature, fitted to the drawn line with the running time and the
transition / minimum-radius rules; design3.py: the formation and structures by their approximate costs; run.py: the running time). This script
only reads those results and writes them in a compact form.

  python3 scripts/fiction_align.py KP_DIR   # KP_DIR: the folder with fit_*.json, design_f*.json, curves_f*.json
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# KP：コマンドでは引数、ほかのスクリプトから関数を使うときは環境変数 FICTION_KP（scripts/fiction_variants.py、2026-11-05）
KP = Path(sys.argv[1] if __name__ == "__main__" else os.environ["FICTION_KP"]).resolve()
sys.path.insert(0, str(KP))
from run import simulate  # noqa: E402  (the running-time model, same as the published figures)

def delta(vals, scale):
    out, last = [], 0
    for v in vals:
        q = round(v * scale)
        out.append(q - last)
        last = q
    return out


def section(sid, name, t, orig_pts, skip_names=(), design=None, alt=None, base=None):
    """A section of the network (2026-11-04: "the alignment first"): its plan and profile, without any running.
    skip_names: stations that belong to the section it branches from (the junction station), not shown twice.
    base: the folder to read from (default KP; the variants of scripts/fiction_variants.py read their own folders, 2026-11-05)"""
    B = Path(base) if base else KP
    fit = json.load(open(B / f"fit_{t}.json"))
    route = json.load(open(B / f"route_f{t}.json"))
    des = json.load(open(B / (design or f"design_f{t}.json")))
    lst = json.load(open(B / f"curvelist_f{t}.json"))
    A = fit["A"]
    alt_ = None
    if alt:   # the profile with all the stations at ground level (the switch on the page, 2026-11-04): formation and structures
        da = json.load(open(B / alt)); alt_ = {"z": [round(q * 10) for q in da["z"]], "struct": da["struct"]}
    return {
        "alt": alt_,
        "id": sid, "name": name,
        # the drawn line (as the user drew it), for comparison
        "orig": {"lon": delta([p[0] for p in orig_pts], 1e5), "lat": delta([p[1] for p in orig_pts], 1e5)},
        # plan: points about every 10 m (1e-5 degree deltas), their chainage (m, on the ground as the profile is) and curvature (1e-7 / m, + = left)
        "lon": delta([p[0] for p in A], 1e5), "lat": delta([p[1] for p in A], 1e5),
        "s": [round(q) for q in route["s"]], "k": [round(q * 1e7) for q in fit["k"]],
        # profile every 20 m: chainage (m), ground and formation (0.1 m), structure (B bridge, T tunnel, - earthwork)
        "ps": [round(q) for q in des["s"]],
        "ground": [None if g is None or (isinstance(g, float) and math.isnan(g)) else round(g * 10) for g in des["ground"]],
        "z": [round(q * 10) for q in des["z"]], "struct": des["struct"],
        "stations": [[n, round(c), 0] for n, c in des["stations"] if n not in skip_names],
        "curves": [[round(c["s0"]), round(c["s1"]), round(c["R"]), c["dir"]] for c in lst],
        "elements": elements(fit, route),
    }


def variant(name, t, lam, dlim):
    fit = json.load(open(KP / f"fit_{t}.json"))
    # chainage on the ground (the same as the profile's): route_f<t>.json from fit2route.py
    route = json.load(open(KP / f"route_f{t}.json"))
    des = json.load(open(KP / f"design_f{t}.json"))
    cv = json.load(open(KP / f"curves_f{t}.json"))
    lst = json.load(open(KP / f"curvelist_f{t}.json"))
    x, v, tt, si, stops, vh = simulate(des, True, cv)
    run = sum(tt[b] - tt[a] for a, b in zip(si, si[1:]))
    A = fit["A"]
    stop_names = set(des["stops"])
    return {
        "name": name, "lam": lam, "D": dlim,
        # plan: points about every 30 m (1e-5 degree deltas), their chainage (m, measured on the ground as the profile is) and curvature (1e-7 / m, + = left)
        "lon": delta([p[0] for p in A], 1e5), "lat": delta([p[1] for p in A], 1e5),
        "s": [round(q) for q in route["s"]], "k": [round(q * 1e7) for q in fit["k"]],
        # profile every 20 m: chainage (m), ground and formation (0.1 m), structure (B bridge, T tunnel, - earthwork)
        "ps": [round(q) for q in des["s"]],
        "ground": [None if g is None or (isinstance(g, float) and math.isnan(g)) else round(g * 10) for g in des["ground"]],
        "z": [round(q * 10) for q in des["z"]], "struct": des["struct"],
        # running every 10 m: the limit (km/h; the train's length kept clear of it) and the express's speed (km/h)
        "dx": 10, "lim": [round(q * 3.6) for q in vh], "v": [round(q * 3.6) for q in v],
        # the limit of the track itself (km/h; before the train's length), for the signs of the limit zones
        "zone": [round(q * 3.6) for q in getattr(simulate, "vl", vh)],
        "stations": [[n, round(c), 1 if n in stop_names else 0] for n, c in des["stations"]],
        # curves: from, to (m), the smallest radius (m), direction
        "curves": [[round(c["s0"]), round(c["s1"]), round(c["R"]), c["dir"]] for c in lst],
        "run_min": round(run / 60, 1),
        # elements (線形要素 only): from, to (m on the ground), kind (S straight, T transition, C circular), radius (m) or
        # for a transition its curvatures at both ends (1e-7 / m)
        "elements": elements(fit, route),
    }


def elements(fit, route):
    if "elements_flat" in fit:   # the intersection-point method (ipfit_all.py): already in order, chainage along the planar alignment
        import numpy as np
        fs, rs = np.array(fit["s"]), np.array(route["s"])
        g = lambda x: round(float(np.interp(x, fs, rs)))
        return [[g(a), g(b), t, x] for a, b, t, x in fit["elements_flat"] if b - a > 0.5]
    if "elements" not in fit:
        return None
    s, out = route["s"], []
    for leg, el in enumerate(fit["elements"]):
        a, b = fit["stopidx"][leg], fit["stopidx"][leg + 1]
        A, X, c = el["A"], el["X"], el["c"]
        local = sum(A) + sum(X); scale = (s[b] - s[a]) / local if local else 1.0  # lengths are planar; chainage on the ground
        pos = s[a]
        for j in range(len(A)):
            if A[j] > 0.5:
                out.append([round(pos), round(pos + A[j] * scale), "C" if c[j] else "S", round(1 / abs(c[j])) if c[j] else 0])
            pos += A[j] * scale
            if j < len(X):
                out.append([round(pos), round(pos + X[j] * scale), "T", [round(c[j] * 1e7), round(c[j + 1] * 1e7)]])
                pos += X[j] * scale
    return out


def car_info(y, ny):
    return {"type": ny["car_type"], "tilt": bool(ny["TILT"]), "cars": ny["cars"], "length": ny["TRAIN"], "vmax": ny["VMAX"]}
def elapsed(v, dx=10):
    t, out = 0.0, [0]
    for a, b in zip(v, v[1:]):
        m = (a + b) / 2 / 3.6; t += dx / m if m > 0.5 else 0; out.append(round(t))
    return out


def main():
    route = json.load(open(KP / "route_shibetoro_heishi.json"))
    NET = json.load(open(KP / "network.json"))
    # sections: the trunk (the express's route, with the station heights) and the branches
    trunk = section("ipg", "特急の経路（蘂取〜紗那〜兵至平）", "ipgh", route["points"], alt="design_fipgh_gs.json")
    sanpu_route = json.load(open(KP / "route_sanpu.json"))
    sanpu = section("sanpu", "散布線（大岬〜瀬石温泉の分岐器）", "sanpu", sanpu_route["points"], skip_names={n for n, *_ in trunk["stations"]},
                    design="design_fsanpu_free.json", alt="design_fsanpu.json")
    shib_route = json.load(open(KP / "route_shibetoro_w.json"))
    shibw = section("shibw", "蘂取線（択捉六甲〜類平）", "shibw", shib_route["points"], skip_names={n for n, *_ in trunk["stations"]},
                    design="design_fshibw_free.json", alt="design_fshibw.json")
    shibr_route = json.load(open(KP / "route_shibetoro_r.json"))
    shibr = section("shibr", "蘂取線（紗那〜沼田〜南留別）", "shibr", shibr_route["points"], skip_names={n for n, *_ in trunk["stations"]},
                    design="design_fshibr_free.json", alt="design_fshibr.json")
    moyoro_route = json.load(open(KP / "route_moyoro.json"))
    moyoro = section("moyoro", "茂世路線（茂世路〜沼田）", "moyoro", moyoro_route["points"], skip_names={n for n, *_ in shibr["stations"]},
                     design="design_fmoyoro_free.json", alt="design_fmoyoro.json")
    def sec_simple(sid, name, route_file, parents):
        """a section added by chain_new2.sh (2026-11-04): the design files design_f<id>_free.json and design_f<id>.json (all the stations at ground level)"""
        rt = json.load(open(KP / route_file))
        return section(sid, name, sid, rt["points"], skip_names={n for P in parents for n, *_ in P["stations"]},
                       design=f"design_f{sid}_free.json", alt=f"design_f{sid}.json")
    rakki = sec_simple("rakki", "酪別線（酪別〜蘂取）", "route_rakkibetsu.json", [trunk])
    toshi = sec_simple("toshi", "茂世路線 冬知里支線（四谷〜塘路）", "route_toshiruri.json", [trunk, moyoro])
    otamoi = sec_simple("otamoi", "小田萌線（年萌〜新指臼）", "route_otamoi.json", [shibw, moyoro])
    sesibe = sec_simple("sesibe", "背蘂線（蘂取〜背祖曽、一部は地形から引いた線）", "route_sesibe.json", [trunk, moyoro])
    tanne = sec_simple("tanne", "丹根萌線（択捉六甲〜丹根萌）", "route_tanne.json", [trunk])
    kuko = sec_simple("kuko", "択捉空港線（西単冠〜択捉空港〜植別）", "route_kuko.json", [shibw])
    # 単冠山口は両側の線が同じ側から入る駅（スイッチバック駅）なので 2 区間（2026-11-05、ユーザーの選択）
    sanroku_n = sec_simple("sanroku_n", "単冠山麓線 北側（入里節〜単冠山口、一部は地形から引いた線）", "route_sanroku_n.json", [shibw])
    sanroku_s = sec_simple("sanroku_s", "単冠山麓線 南側（単冠山口〜長生内、一部は地形から引いた線）", "route_sanroku_s.json", [trunk])
    # 択捉の残り 6 路線（2026-11-06、register6.py が書いた）
    furu = sec_simple("furu", "振別線（老門〜奧羅臼）", "route_furu.json", [trunk])
    atosa_w = sec_simple("atosa_w", "阿登佐線 西側（択捉神居古潭〜内保）", "route_atosa_w.json", [trunk])
    atosa_e1 = sec_simple("atosa_e1", "阿登佐線 東側（択捉神居古潭〜散布泊）", "route_atosa_e1.json", [trunk])
    atosa_e2 = sec_simple("atosa_e2", "阿登佐線 東側（散布泊〜阿登佐岳）", "route_atosa_e2.json", [])
    noto = sec_simple("noto", "野斗路線（振別〜賢萌〜野斗路）", "route_noto.json", [trunk])
    yorib = sec_simple("yorib", "寄別線（焼沼〜鬼門〜寄別）", "route_yorib.json", [otamoi])
    otoshi = sec_simple("otoshi", "乙知志線（乙知志〜択捉原〜北乙）", "route_otoshi.json", [moyoro])
    moke = sec_simple("moke", "萌消線（萌消〜満前）", "route_moke.json", [trunk])
    sections = [trunk, sanpu, shibw, shibr, moyoro, rakki, toshi, otamoi, sesibe, tanne, kuko, sanroku_n, sanroku_s, furu, atosa_w, atosa_e1, atosa_e2, noto, yorib, otoshi, moke]
    SEC_IDX = {S["id"]: i for i, S in enumerate(sections)}
    # systems: the express (the trunk as a whole) and the local train 大岬→紗那 (keito.py: the branch, then the trunk from the junction)
    tk = variant("特急 蘂取→兵至平", "ipgh", 100000, 30)
    tokkyu = {"name": tk["name"], "car": NET["systems"][0]["car"], "path": [[0, 0, trunk["ps"][-1]]],
              "dx": 10, "lim": tk["lim"], "v": tk["v"], "zone": tk["zone"], "run_min": tk["run_min"],
              "stations": tk["stations"]}
    # the express on the profile with all the stations at ground level (the switch)
    _d = json.load(open(KP / "design_fipgh_gs.json")); _cv = json.load(open(KP / "curves_fipgh.json"))
    _x, _v, _tt, _si, _st, _vh = simulate(_d, True, _cv)
    tokkyu["alt"] = {"lim": [round(q * 3.6) for q in _vh], "v": [round(q * 3.6) for q in _v], "zone": [round(q * 3.6) for q in getattr(simulate, "vl", _vh)],
                     "run_min": round(sum(_tt[b] - _tt[a] for a, b in zip(_si, _si[1:])) / 60, 1)}
    kj = json.load(open(KP / "keito_普通大岬紗那_free.json")); kg = json.load(open(KP / "keito_普通大岬紗那_gs.json"))
    st_t = dict((n, c) for n, c, _ in trunk["stations"])
    futsu = {"name": "普通 大岬→紗那", "car": NET["systems"][1]["car"],
             "path": [[1, 0, round(kj["Lb"])], [0, round(kj["sj"]), round(st_t["紗那"])]],
             "dx": 10, "lim": [round(q) for q in kj["lim"]], "v": [round(q) for q in kj["v"]], "zone": [round(q) for q in kj["zone"]],
             "run_min": round(kj["run_min"], 1), "stations": [[n, round(c), 1 if n in kj["stops"] else 0] for n, c in kj["stations"]],
             "alt": {"lim": [round(q) for q in kg["lim"]], "v": [round(q) for q in kg["v"]], "zone": [round(q) for q in kg["zone"]], "run_min": round(kg["run_min"], 1)}}
    # the train table (2026-11-04, the user's request): the car, and the running time from the first station at each point (t, s, every dx; stops
    # excluded, as the running time: dt = dx / the mean speed of the two ends)
    # systems made by keito2.py (2026-11-04): the path as pieces of sections, a piece with from > to running the section backwards
    def system_k2(ny):
        k = json.load(open(KP / f"keito2_{json.load(open(KP / ny['keito2']))['name']}.json"))
        kg = json.load(open(KP / f"keito2_{k['name']}_gs.json"))
        r = lambda a: [round(q) for q in a]
        return {"name": ny["name"], "car": ny["car"], "path": [[SEC_IDX[sec], a, b] for sec, a, b in k["path"]],
                "dx": 10, "lim": r(k["lim"]), "v": r(k["v"]), "zone": r(k["zone"]), "run_min": round(k["run_min"], 1),
                "stations": [[n, round(c), 1 if n in k["stops"] else 0] for n, c in k["stations"]],
                "alt": {"lim": r(kg["lim"]), "v": r(kg["v"]), "zone": r(kg["zone"]), "run_min": round(kg["run_min"], 1)}}
    NETS = {y["id"]: y for y in NET["systems"]}
    K2 = ("tokkyu_moyoro", "futsu_shibetoro", "tokkyu_rakki", "kyuko", "kaisoku_kuko", "futsu_tokite", "futsu_sanroku", "futsu_furu", "futsu_atosa", "futsu_noto", "futsu_yorib", "futsu_otoshi", "futsu_moke")
    k2 = [system_k2(NETS[i]) for i in K2]
    for y, ny in [(tokkyu, NETS["tokkyu"]), (futsu, NETS["futsu_sanpu"])] + [(k, NETS[i]) for k, i in zip(k2, K2)]:
        y["train"] = car_info(y, ny); y["t"] = elapsed(y["v"])[::10]; y["tdx"] = 100   # every 100 m (the page interpolates), to keep the data small
        if "alt" in y: y["alt"]["t"] = elapsed(y["alt"]["v"])[::10]
        print(y["name"], "経過時間の終わり", round(y["t"][-1] / 60, 1), "分（走行時間", y["run_min"], "分）")
    out = {
        "source": "架空路線（data/fiction_src）と地理院の標高（DEM10B）から、作業用のリポジトリ（eki-radar/fiction/kp）で設計",
        "license": "— （架空。テスト版と手元のビルドだけ）",
        "note": "まず線形ありき：線路網を、分岐する点と線の端で区切った区間（sections）ごとに平面・縦断を 1 つ持ち、系統（systems：通る区間の範囲と、車両の条件での制限速度・速度・所要時間）はその上に乗る。平面は交点法：元の折れ線を 30 m の幅で簡略化した直線を、交点ごとに規格の曲線（緩和曲線＋円曲線＋緩和曲線、半径 160〜5000 m の 10 m 刻み）でつなぎ、交点を動かす・取り除く・まとめる手で、元の折れ線からのずれ（上限 D＝30 m）と走行時間の釣り合いを取る。駅は線形を描いたあとに射影する。支線は、本線の線形の上の分岐器の位置から、本線の向きに 12 番の分岐器の角度を加えた向きで始める。曲線の制限速度は、振子式（特急）は半径 600 m 以上が本則＋30、未満が √(215R/11.8)、本則（普通）は √(165R/11.8)、余裕 1 km/h を引いて 5 km/h 単位に切り捨て。制限速度区間は、円曲線の制限を前後の緩和曲線の始点から終点までにかける（標識の位置。走行もこれに従う）。緩和曲線は X ≥ max(0.4C, 0.007CV)。縦断は構造物の概算費用（特急の経路は複線、散布線は単線）で土工・トンネル・橋梁を選び、勾配は 15‰ を原則に 25‰ まで",
        "built_with": (ROOT / "data" / "VERSION").read_text().strip(),
        "sections": sections,
        "systems": [tokkyu, futsu] + k2,
    }
    p = ROOT / "data" / "fiction_align.json"
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(p, round(p.stat().st_size / 1024), "KB;", ", ".join(f"{v['name']} {v['run_min']} 分" for v in out["systems"]))


if __name__ == "__main__":
    main()
