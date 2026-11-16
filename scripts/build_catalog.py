#!/usr/bin/env python3
"""Writes data/catalog.json: every project Port Watch lists, fully resolved, for programs that can't run the page's
own JavaScript (Port Launcher reads it). Built only from files already in the repository, so it makes no requests:
the built-in list, overrides.json and the data/ files the refresh has just written.

Called at the end of refresh_data.py; can also be run by hand:  python3 scripts/build_catalog.py
(run by hand, projects that only Awesome Decomp Games lists are taken from the previous catalog).

The rules here are simpler than the page's (no repo-name guessing, no automatic XBLA detection), so the page stays the
reference; where they differ, fix the project in overrides.json and both agree.
"""
import datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "catalog.json")
DESKTOP = ("Windows", "Linux", "macOS", "Steam Deck")
FEATURE_LABELS = {"hfr": "High refresh rate", "aspect": "Aspect ratios", "hdr": "HDR", "res": "Higher resolution", "dlss": "DLSS", "fsr": "FSR",
                  "xess": "XeSS", "fg": "Frame generation", "rt": "Ray tracing", "tex": "Texture packs", "mods": "Mod support",
                  "kbm": "Keyboard and mouse", "online": "Online play", "gyro": "Gyro aiming", "aa": "Anti-aliasing", "dlc": "DLC support",
                  "single": "Single-screen"}
# kept in step with FAMOUS_ALIASES in index.html
FAMOUS = {"shipofharkinian": "HarbourMasters/Shipwright", "shipwright": "HarbourMasters/Shipwright", "2ship2harkinian": "HarbourMasters/2ship2harkinian",
          "zelda64recomp": "Zelda64Recomp/Zelda64Recomp", "spaghettikart": "HarbourMasters/SpaghettiKart", "starship": "HarbourMasters/Starship",
          "ghostship": "HarbourMasters/Ghostship", "opengoal": "open-goal/jak-project", "unleashedrecomp": "hedge-dev/UnleashedRecomp",
          "marathonrecomp": "sonicnext-dev/MarathonRecomp", "banjorecomp": "BanjoRecomp/BanjoRecomp", "sm64coopdx": "coop-deluxe/sm64coopdx",
          "dusklight": "TwilitRealm/dusklight", "rexglue": "rexglue/rexglue-sdk", "xenonrecomp": "hedge-dev/XenonRecomp", "n64recomp": "N64Recomp/N64Recomp",
          "perfectdark": "perfect-dark-pc-port/perfect_dark", "skate3recomp": "mchughalex/skate3recomp"}


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(t or "").lower())).strip()


def link_of(k):
    if k.startswith("link:"):
        return k[5:]
    if k.startswith(("gitlab.com/", "itch.io/", "sourceforge.net/")):
        if k.startswith("sourceforge.net/"):
            return "https://sourceforge.net/projects/" + k.split("/", 1)[1] + "/"
        return "https://" + k
    return "https://github.com/" + k


def impersonates(k, stars):
    if (stars or 0) >= 50 or "/" not in k:
        return ""
    owner, repo = k.replace("gitlab.com/", "").split("/")[:2]
    name = re.sub(r"[^a-z0-9]", "", repo.lower())
    for n, full in FAMOUS.items():
        if full.split("/")[0].lower() != owner and len(n) >= 6 and n in name:
            return full
    return ""


def lure_risk(k, st, stars, now):
    """Port of lureRiskOf() in index.html."""
    if not st or k.startswith("itch.io/"):
        return None
    r, sig, reasons, sc = st.get("repo") or {}, st.get("readmeLure") or [], [], 0
    no_code = r.get("size") is not None and r["size"] <= 50 and not r.get("lang")
    if no_code: sc += 2; reasons.append("almost no content and no code")
    if "badges" in sig: sc += 3; reasons.append("fake download or rating badges")
    if "offsite" in sig: sc += 3; reasons.append("download links that lead to another website")
    if "filehost" in sig: sc += 2; reasons.append("links to file-hosting or link-shortening sites")
    if "password" in sig: sc += 3; reasons.append("a password-protected download")
    imp = impersonates(k, stars)
    if imp: sc += 2; reasons.append("its name copies " + imp)
    try:
        age = (now - datetime.datetime.fromisoformat(r["created"].replace("Z", "+00:00"))).days
        if age <= 30 and (stars or 0) <= 3: sc += 1; reasons.append("created in the last 30 days with almost no stars")
    except Exception:
        pass
    if r.get("lang") and (r.get("size") is None or r["size"] >= 200):
        sc -= 3
    strong = no_code or "badges" in sig or "offsite" in sig
    if sc >= 6 and strong:
        return {"level": "high", "reasons": reasons}
    if sc >= 3 and (sig or imp):
        return {"level": "medium", "reasons": reasons}
    return None


def lt_url(e, folder="Named_Boxarts"):
    if not e or not e.get("file") or not e.get("repo"):
        return ""
    from urllib.parse import quote
    branch = "main" if e["repo"] == "Sega_-_Naomi_2" else "master"
    return f"https://raw.githubusercontent.com/libretro-thumbnails/{e['repo']}/{branch}/{folder}/{quote(e['file'], safe='')}"


def igdb(image_id, size):
    return f"https://images.igdb.com/igdb/image/upload/t_{size}/{image_id}.jpg"


def build(projects=None):
    """projects: the refresh's full list (built-in + Awesome Decomp Games + added + Decomp Buddy). None = rebuild from files."""
    import refresh_data as R
    now = datetime.datetime.now(datetime.timezone.utc)
    ov_file = R.load_json(os.path.join(ROOT, "overrides.json"), {}) or {}
    fixes, added_raw = ov_file.get("projects") or {}, {k.lower(): v for k, v in (ov_file.get("added") or {}).items() if isinstance(v, dict)}
    status = (load("status.json", {}).get("repos")) or {}
    covers = load("covers.json", {}).get("covers") or {}
    lt = load("libretro.json", {}).get("map") or {}
    art = load("art.json", {}).get("art") or {}
    sgdb = lambda key: {x: v for x, v in (art.get(key) or {}).items() if x in ("hero", "logo", "icon", "wide", "capsule")}
    screens = load("screens.json", {})
    smap, sgames = screens.get("map") or {}, screens.get("games") or {}
    seen = load("history.json", {}).get("seen") or {}
    previous = {p["k"]: p for p in (load("catalog.json", {}).get("projects") or [])}

    if projects is None:
        seed = R.seed_projects()
        known = {p.get("k") for p in seed}
        dbuddy = [p for p in (load("decompbuddy.json", {}).get("projects") or []) if p.get("k") not in known]
        added = [p for p in R.load_added() if p["k"] not in known]
        projects = seed + added + dbuddy
        have = {p.get("k") for p in projects}
        # Awesome-only projects can't be listed without a request: keep them as the last catalog had them
        carried = [p for k, p in previous.items() if k not in have and p.get("source") == "Awesome Decomp Games"]
    else:
        carried = []

    out, done = [], set()
    for p in projects:
        k = (p.get("k") or p.get("id") or "").lower()
        if not k or k in done:
            continue
        done.add(k)
        a = added_raw.get(k) or {}
        fix = {**{x: a[x] for x in ("title", "platform", "type", "pcRelease", "runsOn", "cover", "games", "region", "note", "mirrors", "hack") if a.get(x) is not None},
               **(fixes.get(k) or fixes.get(p.get("id") or "") or {})}
        if fix.get("hide"):
            continue
        st = status.get(k) or {}
        if st.get("notFound"):
            continue
        repo, readme = st.get("repo") or {}, st.get("readme") or {}
        stars = repo.get("stars") if repo.get("stars") is not None else (p.get("stars") or 0)
        title = str(fix.get("title") or p.get("g") or k.split("/")[-1])
        platform = fix.get("platform") or p.get("p") or "Unknown"
        # what it runs on: a shared fix wins; then the list's own value and release files; README only fills in desktop systems
        po = p.get("po") or []
        if isinstance(po, str):
            po = [x.strip() for x in po.split(",") if x.strip()]
        if isinstance(fix.get("runsOn"), list):
            runs, runs_src = list(fix["runsOn"]), "fix"
        else:
            strong = list(dict.fromkeys(list(po) + list((st.get("assetOs") or {}).keys())))
            weak = list((readme.get("os") or {}).keys())
            if strong:
                runs, runs_src = strong, "release"
                if any(x in strong for x in ("Windows", "Linux", "macOS")):
                    runs += [x for x in DESKTOP if x in weak and x not in runs]
            else:
                runs, runs_src = weak, "readme"
        rel = st.get("release") or ({"tag": p["rel"], "date": p.get("rd") or "", "url": "", "pre": bool(p.get("pre"))} if p.get("rel") else None)
        sg = sgames.get(smap.get(k) or "") or {}
        cov = covers.get(k) or {}
        cover = fix.get("cover") or lt_url(lt.get(k)) or cov.get("url") or (igdb(sg["cover"], "cover_big") if sg.get("cover") else "")
        feats = readme.get("features") or {}
        games = []
        for g in R.games_of(p, fix):
            gk = f"{k}#{R.norm(g['title'])}"
            gs = sgames.get(smap.get(gk) or "") or {}
            gcov = (fix.get("gameCovers") or {}).get(g["title"]) or lt_url(lt.get(gk)) or (covers.get(gk) or {}).get("url") or (igdb(gs["cover"], "cover_big") if gs.get("cover") else "")
            games.append({"title": g["title"], "platform": g["platform"], "cover": gcov, "sgdb": sgdb(gk),
                          "art": [igdb(i, "1080p") for i in (gs.get("art") or [])[:2]] or [igdb(i, "1080p") for i in (gs.get("shots") or [])[:1]]})
        source = "Port Watch" if p.get("src") or k in added_raw else ("Decomp Buddy" if str(p.get("id") or "").startswith("db:") else "Awesome Decomp Games")
        out.append({
            "k": k, "title": title, "platform": platform, "type": fix.get("type") or p.get("t") or a.get("type") or "",
            "link": a.get("link") or p.get("l") or (("https://github.com/" + repo["full"]) if repo.get("full") and "/" in k and "." not in k.split("/")[0] else link_of(k)),
            "desc": a.get("description") or repo.get("desc") or p.get("d") or "",
            "pcRelease": fix.get("pcRelease") or p.get("ps") or "",
            "runsOn": runs, "runsOnFrom": runs_src,
            "features": sorted(f for f, v in feats.items() if v == "yes"),
            "planned": sorted(f for f, v in feats.items() if v == "planned"),
            "release": rel, "playable": bool(rel), "pushed": repo.get("pushed") or p.get("lc") or "",
            "stars": stars, "archived": bool(repo.get("archived")),
            "sgdb": sgdb(k), "cover": cover, "coverThumb": cov.get("thumb") if cover == cov.get("url") else "",
            "art": [igdb(i, "1080p") for i in (sg.get("art") or [])[:2]] or [igdb(i, "1080p") for i in (sg.get("shots") or [])[:1]],
            "shots": {"port": (st.get("shots") or [])[:8], "original": [igdb(i, "screenshot_big") for i in (sg.get("shots") or [])[:6]]},
            "genres": sg.get("genres") or [], "series": sg.get("series") or [],
            "nsfw": fix["nsfw"] if isinstance(fix.get("nsfw"), bool) else bool(sg.get("nsfw")),
            "risk": lure_risk(k, st, stars, now),
            "games": games, "hack": fix.get("hack") or p.get("hack") or "", "note": fix.get("note") or "",
            "mirrors": fix.get("mirrors") or [], "firstSeen": seen.get(k) or "", "source": source,
        })
    out += [p for p in carried if p["k"] not in done]
    out.sort(key=lambda p: (norm(p["title"]), p["k"]))
    doc = {"format": "port-watch-catalog", "version": 1, "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "featureLabels": FEATURE_LABELS, "projects": out}
    changed = R.write_json_if_changed(OUT, doc)
    R.log(f"  catalog.json: {len(out)} projects" + ("" if changed is None or changed else " (unchanged)"))
    return doc


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    build()
