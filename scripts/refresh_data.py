#!/usr/bin/env python3
"""Refresh Port Watch's shared data files. Runs in GitHub Actions (see .github/workflows/refresh-data.yml).

- data/covers.json  SteamGridDB covers for games without libretro box art (needs the SGDB_API_KEY secret)
- data/itch.json    the latest devlog posts of projects hosted on itch.io

Only the Python standard library is used. Files are rewritten only when their contents change,
so runs with nothing new make no commit.
"""
import datetime, difflib, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
INDEX = os.path.join(ROOT, "index.html")
SGDB_BASE = os.environ.get("SGDB_BASE", "https://www.steamgriddb.com/api/v2")
AWESOME_URL = os.environ.get("PW_AWESOME_URL", "https://raw.githubusercontent.com/SubmitGame/awesome-decomp-games/main/data/games.json")
ITCH_BASE = os.environ.get("PW_ITCH_BASE", "https://{user}.itch.io")   # overridable for local testing only
MAX_LOOKUPS = int(os.environ.get("PW_MAX_LOOKUPS", "250"))              # SteamGridDB lookups per run
RETRY_MISSES_DAYS = 14
UA = "port-watch-refresh/1.0 (+https://github.com)"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# ---------------------------------------------------------------- helpers
def log(*a): print(*a, flush=True)

def http_get(url, headers=None, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise
            if e.code == 404:
                return None
            if e.code == 429 and attempt < tries - 1:
                time.sleep(int(e.headers.get("Retry-After", "10")))
                continue
            if attempt == tries - 1:
                raise
        except urllib.error.URLError:
            if attempt == tries - 1:
                raise
        time.sleep(2 * (attempt + 1))
    return None

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

def write_json_if_changed(path, obj, compare_without=("generated",)):
    old = load_json(path, None)
    strip = lambda o: {k: v for k, v in (o or {}).items() if k not in compare_without} if isinstance(o, dict) else o
    if old is not None and strip(old) == strip(obj):
        log(f"  {os.path.relpath(path, ROOT)}: unchanged")
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    log(f"  {os.path.relpath(path, ROOT)}: updated")
    return True

def norm(t):
    t = "".join(c for c in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(c)).lower().replace("&", " and ")
    t = re.sub(r"[’'`]", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return re.sub(r"^the ", "", t)

ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10"}
def numbers(t): return sorted(ROMAN.get(w, w) for w in t.split() if w.isdigit() or w in ROMAN)

def strip_parens(t):
    prev = None
    while prev != t:
        prev, t = t, re.sub(r"\s*\((?!\d{4}\))[^()]*\)\s*$", "", t).strip()
    return t
SUFFIX = re.compile(r"[\s-]+(re-?compiled|recomp|recompilation|static recomp|pc port|native port|port|pc|decomp|decompilation|native|hd remaster|android|enhanced)$", re.I)
def cover_title(t):
    t = strip_parens(t or "")
    prev = None
    while prev != t:
        prev, t = t, SUFFIX.sub("", t).strip()
    return t

# ---------------------------------------------------------------- what Port Watch tracks
def seed_projects():
    html = open(INDEX, encoding="utf-8").read()
    m = re.search(r"const SEED = (\[.*?\]);\nconst BUILT", html, re.S)
    if not m:
        sys.exit("Couldn't find Port Watch's built-in list in index.html.")
    return json.loads(m.group(1).replace("<\\/", "</"))

AW_PLAT = {"N64": "N64", "N64 / GameCube": "N64", "Xbox 360": "Xbox 360", "xbox360": "Xbox 360", "PS1": "PS1", "ps": "PS1", "GameCube": "GameCube",
           "GBA": "GBA", "PS2": "PS2", "NES": "NES", "Wii": "Wii", "DS": "DS", "SNES": "SNES", "Game Boy Color": "Game Boy Color", "Game Boy": "Game Boy",
           "Genesis": "Mega Drive", "Xbox": "Xbox (original)", "og xbox": "Xbox (original)", "Switch": "Switch", "Wii U": "Wii U", "PS3": "PS3", "PS4": "PS4",
           "Arcade": "Arcade", "3DS": "3DS", "Dreamcast": "Dreamcast", "PSP": "PSP", "32X": "32X", "Virtual Boy": "Virtual Boy", "Game Gear": "Game Gear",
           "Saturn": "Saturn", "Master System": "Master System"}
AW_PLAT_FIX = {"supermedo/bloodborne_pc": "PS4", "chasem-dev/sms-launcher": "GameCube", "wurlyfox/c1": "PS1", "999sian/melee-pc": "GameCube"}

def awesome_projects():
    try:
        d = json.loads(http_get(AWESOME_URL) or b"{}")
    except Exception as e:
        log(f"  Awesome Decomp Games couldn't be read ({e}); using the built-in list only")
        return []
    out = []
    for g in d.get("games", []):
        t = {"static-recomp": "Recompilation", "source-port": "Decompilation"}.get(g.get("type"))
        if g.get("type") == "decompilation" and g.get("release"):
            t = "Decompilation"
        if not t or not g.get("repo"):
            continue
        k = ("gitlab.com/" if "gitlab.com" in (g.get("url") or "") else "") + g["repo"].lower()
        p = AW_PLAT_FIX.get(k) or AW_PLAT.get(g.get("platform"))
        if p:
            out.append({"k": k, "id": "aw:" + k, "g": g.get("title") or "", "p": p})
    return out

# ---------------------------------------------------------------- SteamGridDB covers
def sgdb_lookup(title, key):
    res = http_get(SGDB_BASE + "/search/autocomplete/" + urllib.parse.quote(title, safe=""), {"Authorization": "Bearer " + key})
    hits = (json.loads(res).get("data") if res else None) or []
    q, best = norm(title), None
    for h in hits:
        n = norm(h.get("name", ""))
        score = 1.0 if n == q else difflib.SequenceMatcher(None, q, n).ratio()
        if numbers(q) != numbers(n):
            score -= 0.3
        if best is None or score > best[0]:
            best = (score, h)
    if not best or best[0] < 0.85:
        return None
    score, hit = best
    time.sleep(0.25)
    res = http_get(f"{SGDB_BASE}/grids/game/{hit['id']}?dimensions=600x900,342x482,660x930&types=static&nsfw=false&humor=false&epilepsy=false",
                   {"Authorization": "Bearer " + key})
    imgs = (json.loads(res).get("data") if res else None) or []
    if not imgs:
        return None
    return {"url": imgs[0].get("url"), "thumb": imgs[0].get("thumb"), "name": hit.get("name"), "match": round(score, 3)}

def refresh_covers(projects):
    key = os.environ.get("SGDB_API_KEY", "").strip()
    path = os.path.join(DATA, "covers.json")
    data = load_json(path, {"format": "port-watch-covers", "version": 1, "covers": {}, "misses": {}})
    covers, misses = data.setdefault("covers", {}), data.setdefault("misses", {})
    if not key:
        log("  SGDB_API_KEY isn't set; skipping covers")
        return False
    todo, seen = [], set()
    for p in projects:
        if p.get("cv"):
            continue                      # already has libretro box art
        ck = p.get("k") or p["id"]
        if ck in seen or ck in covers:
            continue
        seen.add(ck)
        miss = misses.get(ck)
        if miss and (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(miss.replace("Z", "+00:00"))).days < RETRY_MISSES_DAYS:
            continue
        title = cover_title(p.get("g", ""))
        if title:
            todo.append((ck, title))
    log(f"  {len(todo)} games need a cover lookup (max {MAX_LOOKUPS} this run)")
    for ck, title in todo[:MAX_LOOKUPS]:
        try:
            hit = sgdb_lookup(title, key)
            bare = re.sub(r"\s*\(\d{4}\)\s*$", "", title)
            if not hit and bare != title:          # "Saints Row (2006)" -> "Saints Row" when the year finds nothing
                time.sleep(0.25)
                hit = sgdb_lookup(bare, key)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log("  SteamGridDB rejected the API key (401); stopping cover lookups")
                break
            log(f"  {title}: SteamGridDB error {e.code}")
            continue
        except Exception as e:
            log(f"  {title}: {e}")
            continue
        if hit and hit.get("url"):
            covers[ck] = {**hit, "title": title, "added": NOW}
            misses.pop(ck, None)
            log(f"  + {title} -> {hit['name']} ({hit['match']})")
        else:
            misses[ck] = NOW
        time.sleep(0.25)
    data["generated"] = NOW
    return write_json_if_changed(path, data)

# ---------------------------------------------------------------- itch.io devlogs
def refresh_itch(projects):
    path = os.path.join(DATA, "itch.json")
    data = load_json(path, {"format": "port-watch-itch", "version": 1, "feeds": {}})
    feeds = data.setdefault("feeds", {})
    for p in projects:
        k = p.get("k") or ""
        if not k.startswith("itch.io/"):
            continue
        _, user, game = k.split("/", 2)
        url = ITCH_BASE.format(user=user) + f"/{game}/devlog.rss"
        try:
            raw = http_get(url)
            if not raw:
                raise ValueError("no feed")
            root = ET.fromstring(raw)
            items = []
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                try:
                    pub = datetime.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                except ValueError:
                    pass
                items.append({"t": title, "d": pub, "u": (it.findtext("link") or "").strip()})
            items = items[:10]
            if items != (feeds.get(k) or {}).get("items"):
                feeds[k] = {"items": items, "fetched": NOW}
                log(f"  {k}: {len(items)} posts, newest: {items[0]['t'] if items else '-'}")
            else:
                log(f"  {k}: no new posts")
        except Exception as e:
            log(f"  {k}: couldn't read the devlog ({e}); keeping the previous copy")
    data["generated"] = NOW
    return write_json_if_changed(path, data)

# ---------------------------------------------------------------- main
def main():
    seed = seed_projects()
    known = {p.get("k") for p in seed if p.get("k")}
    extra = [p for p in awesome_projects() if p["k"] not in known]
    log(f"Port Watch list: {len(seed)} built-in projects, {len(extra)} newer ones from Awesome Decomp Games")
    log("Covers:")
    refresh_covers(seed + extra)
    log("itch.io devlogs:")
    refresh_itch(seed)

if __name__ == "__main__":
    main()
