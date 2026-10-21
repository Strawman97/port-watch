#!/usr/bin/env python3
"""Refresh Port Watch's shared data files. Runs in GitHub Actions (see .github/workflows/refresh-data.yml).

- data/covers.json  SteamGridDB covers for games without libretro box art (needs the SGDB_API_KEY secret)
- data/itch.json    the latest devlog posts of projects hosted on itch.io
- data/status.json  every tracked GitHub/GitLab project's latest release, activity, README features and platforms,
                    so visitors can check for updates without their own GitHub token (uses the workflow's GITHUB_TOKEN)

Only the Python standard library is used. Files are rewritten only when their contents change,
so runs with nothing new make no commit.
"""
import datetime, difflib, json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pw_analysis as A

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
# Years each console's games came out, used to pick between same-named games ("FIFA Street" 2005 vs 2012).
PLATFORM_ERA = {"PS1": (1994, 2006), "PS2": (2000, 2013), "PS3": (2006, 2017), "PS4": (2013, 2023), "PSP": (2004, 2014), "PS Vita": (2011, 2019),
                "Xbox (original)": (2001, 2008), "Xbox 360": (2005, 2016), "XBLA (Xbox 360)": (2004, 2016), "Xbox One": (2013, 2022),
                "NES": (1983, 1995), "SNES": (1990, 1999), "N64": (1996, 2002), "GameCube": (2001, 2007), "Wii": (2006, 2014), "Wii U": (2012, 2017),
                "Switch": (2017, 2030), "Game Boy": (1989, 2001), "Game Boy Color": (1998, 2003), "GBA": (2001, 2008), "DS": (2004, 2014),
                "3DS": (2011, 2020), "Mega Drive": (1988, 1998), "32X": (1994, 1996), "Saturn": (1994, 2000), "Dreamcast": (1998, 2002),
                "Master System": (1985, 1996), "Game Gear": (1990, 1997), "Virtual Boy": (1995, 1996), "Mobile": (2008, 2030)}
EXTRA_WORDS = re.compile(r"\b(mini|demake|hack|remake|remaster(ed)?|reloaded|fan ?made|deluxe|hd|definitive|collection|anniversary|redux|3d|online|portable)\b", re.I)

def vnorm(t):
    """norm() without a trailing "version": "Pokémon Emerald" matches "Pokémon Emerald Version"."""
    return re.sub(r" version$", "", norm(t))

def bare_title(t):
    return re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)", " ", t or "")).strip()

def title_year(t):
    m = re.search(r"\((?:[^)]*\D)?((?:19|20)\d\d)\)", t or "")
    return int(m.group(1)) if m else None

def pick_match(title, cands, name_of, year_of, platform, threshold=0.88):
    """Best candidate for a title: names compared without brackets; a year in the title, or else the console's era,
    chooses between same-named games; extra words such as "mini" or "remake" count against a candidate."""
    q = vnorm(bare_title(title)); want = title_year(title); era = PLATFORM_ERA.get(platform)
    q_extra = {m.group(0).lower() for m in EXTRA_WORDS.finditer(bare_title(title))}
    best = None
    for c in cands or []:
        raw = name_of(c) or ""
        n = vnorm(bare_title(raw))
        score = 1.0 if n == q else difflib.SequenceMatcher(None, q, n).ratio()
        if numbers(q) != numbers(n):
            score -= 0.3
        if {m.group(0).lower() for m in EXTRA_WORDS.finditer(bare_title(raw))} - q_extra:
            score -= 0.2
        y = year_of(c) or title_year(raw)
        rank = score
        if want and y:
            rank += 0.2 if abs(y - want) <= 1 else -0.25
        elif era and y:
            rank += 0.05 if era[0] <= y <= era[1] else -0.15
        if score >= threshold and (best is None or rank > best[0]):
            best = (rank, score, c)
    return (best[1], best[2]) if best else None

def ts_year(v):
    try:
        return datetime.datetime.fromtimestamp(int(v), datetime.timezone.utc).year if v else None
    except (ValueError, OSError, OverflowError):
        return None

def sgdb_lookup(title, key, platform=""):
    res = http_get(SGDB_BASE + "/search/autocomplete/" + urllib.parse.quote(bare_title(title), safe=""), {"Authorization": "Bearer " + key})
    hits = (json.loads(res).get("data") if res else None) or []
    best = pick_match(title, hits, lambda h: h.get("name"), lambda h: ts_year(h.get("release_date")), platform)
    if not best:
        return None
    score, hit = best
    time.sleep(0.25)
    res = http_get(f"{SGDB_BASE}/grids/game/{hit['id']}?dimensions=600x900,342x482,660x930&types=static&nsfw=false&humor=false&epilepsy=false",
                   {"Authorization": "Bearer " + key})
    imgs = (json.loads(res).get("data") if res else None) or []
    if not imgs:
        return None
    return {"url": imgs[0].get("url"), "thumb": imgs[0].get("thumb"), "name": hit.get("name"), "match": round(score, 3), "rev": 2}

def load_overrides():
    """Shared fixes from overrides.json in the repository root (title, cover, platform, type, pcRelease, runsOn, hide)."""
    return (load_json(os.path.join(ROOT, "overrides.json"), {}) or {}).get("projects") or {}

def games_of(p, fix):
    """Other games a project covers: [{title, platform}] from a shared fix or the added entry."""
    raw = fix.get("games") if fix.get("games") is not None else p.get("games")
    out = []
    for e in raw or []:
        if isinstance(e, dict):
            t, pl = str(e.get("title") or "").strip(), str(e.get("platform") or "").strip()
        else:
            t, _, pl = str(e).partition("|")
            t, pl = t.strip(), pl.strip()
        if t:
            out.append({"title": t, "platform": pl or p.get("p") or ""})
    return out

def with_games(projects, overrides):
    """Each extra game becomes its own entry (key k#title) so it gets a cover and screenshots."""
    out = list(projects)
    for p in projects:
        key = p.get("k") or p["id"]
        fix = overrides.get(key) or overrides.get(p["id"]) or {}
        if fix.get("hide"):
            continue
        for g in games_of(p, fix):
            gk = f"{key}#{norm(g['title'])}"
            out.append({"k": gk, "id": gk, "g": g["title"], "p": g["platform"], "ghost": True})
    return out

def load_added():
    """Projects the maintainer added for everyone (the "added" section of overrides.json)."""
    out = []
    for key, e in ((load_json(os.path.join(ROOT, "overrides.json"), {}) or {}).get("added") or {}).items():
        if not isinstance(e, dict) or key.startswith("link:"):
            continue                      # links that aren't GitHub, GitLab or itch.io can't be checked
        k = key.lower()
        out.append({"k": k, "id": "shared:" + k, "g": e.get("title") or k.split("/")[-1], "p": e.get("platform") or "Unknown",
                    "cover": e.get("cover") or "", "games": e.get("games") or []})
    return out

def refresh_covers(projects, overrides):
    key = os.environ.get("SGDB_API_KEY", "").strip()
    path = os.path.join(DATA, "covers.json")
    data = load_json(path, {"format": "port-watch-covers", "version": 1, "covers": {}, "misses": {}})
    covers, misses = data.setdefault("covers", {}), data.setdefault("misses", {})
    if not key:
        log("  SGDB_API_KEY isn't set; skipping covers")
        return False
    todo, seen = [], set()
    for p in projects:
        ck = p.get("k") or p["id"]
        fix = overrides.get(ck) or overrides.get(p["id"]) or {}
        if fix.get("hide") or fix.get("cover"):
            covers.pop(ck, None)          # hidden, or the maintainer pinned a cover: nothing to look up
            continue
        fixed_title = cover_title(fix["title"]) if fix.get("title") else ""
        if p.get("cv") and not fixed_title:
            continue                      # already has libretro box art
        if ck in seen:
            continue
        seen.add(ck)
        plat = fix.get("platform") or p.get("p") or ""
        if ck in covers:
            if fixed_title and covers[ck].get("title") != fixed_title:
                covers.pop(ck, None)      # the title was corrected: look the cover up again
                misses.pop(ck, None)
            elif covers[ck].get("rev") == 2:
                continue
            else:
                todo.append((ck, covers[ck].get("title") or cover_title(p.get("g", "")), plat))   # matched by the older rules: check once more
                continue
        miss = misses.get(ck)
        if miss and (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(miss.replace("Z", "+00:00"))).days < RETRY_MISSES_DAYS:
            continue
        title = fixed_title or cover_title(p.get("g", ""))
        if title:
            todo.append((ck, title, plat))
    log(f"  {len(todo)} games need a cover lookup (max {MAX_LOOKUPS} this run)")
    for ck, title, plat in todo[:MAX_LOOKUPS]:
        old = covers.get(ck)
        try:
            hit = sgdb_lookup(title, key, plat)
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
            if not old or old.get("url") != hit["url"]:
                log(f"  + {title} -> {hit['name']} ({hit['match']})")
        elif old and old.get("match", 0) >= 0.95 and not EXTRA_WORDS.search(old.get("name") or ""):
            covers[ck] = {**old, "rev": 2}  # the new rules found nothing better: keep a confident older match
        else:
            covers.pop(ck, None)
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

# ---------------------------------------------------------------- shared update checks
GQL_URL = os.environ.get("PW_GQL_URL", "https://api.github.com/graphql")
GITLAB_API = os.environ.get("PW_GITLAB_API", "https://gitlab.com/api/v4")
README_NAMES = ["README.md", "readme.md", "Readme.md", "README.MD", "README", "README.markdown", "README.rst", "README.txt"]
RELEASE_FIELDS = "tagName publishedAt createdAt isPrerelease url releaseAssets(first: 40) { nodes { name } }"


def gql(query, token):
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(GQL_URL, data=body, headers={"Authorization": "bearer " + token, "Content-Type": "application/json", "User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def not_found_aliases(resp):
    return {e["path"][0] for e in (resp.get("errors") or []) if e.get("type") == "NOT_FOUND" and e.get("path")}


def repo_ref(k):
    owner, name = k.split("/", 1)
    return "repository(owner: %s, name: %s)" % (json.dumps(owner), json.dumps(name))


def meta_batch(keys, token):
    parts = ["r%d: %s { nameWithOwner pushedAt stargazerCount isArchived description diskUsage createdAt primaryLanguage { name } "
             "releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { %s } } }" % (i, repo_ref(k), RELEASE_FIELDS)
             for i, k in enumerate(keys)]
    resp = gql("query {\n" + "\n".join(parts) + "\n}", token)
    data, missing = resp.get("data") or {}, not_found_aliases(resp)
    out = {}
    for i, k in enumerate(keys):
        a = "r%d" % i
        if a in missing:
            out[k] = {"notFound": True}
            continue
        r = data.get(a)
        if not r:
            continue                      # some other error: keep the previous entry
        rel = ((r.get("releases") or {}).get("nodes") or [None])[0]
        e = {"repo": {"pushed": r.get("pushedAt"), "stars": r.get("stargazerCount"), "archived": bool(r.get("isArchived")),
                      "full": r.get("nameWithOwner"), "desc": r.get("description") or "", "size": r.get("diskUsage"),
                      "lang": (r.get("primaryLanguage") or {}).get("name"), "created": r.get("createdAt")}}
        if rel:
            e["release"] = {"tag": rel.get("tagName"), "date": rel.get("publishedAt") or rel.get("createdAt"),
                            "pre": bool(rel.get("isPrerelease")), "url": rel.get("url")}
            e["assetOs"] = A.os_from_assets([n["name"] for n in ((rel.get("releaseAssets") or {}).get("nodes") or [])])
        else:
            e["noRelease"] = True
        out[k] = e
    return out


def readme_batch(keys, token, full_names=None):
    full_names = full_names or {}
    parts = []
    for i, k in enumerate(keys):
        files = " ".join('f%d: object(expression: %s) { ... on Blob { text } }' % (j, json.dumps("HEAD:" + n)) for j, n in enumerate(README_NAMES))
        man = ('m0: object(expression: "HEAD:.recomp.json") { ... on Blob { text } } '
               'm1: object(expression: "HEAD:.recomp-board.json") { ... on Blob { text } }')
        parts.append("r%d: %s { %s %s }" % (i, repo_ref(k), files, man))
    resp = gql("query {\n" + "\n".join(parts) + "\n}", token)
    data = resp.get("data") or {}
    out = {}
    for i, k in enumerate(keys):
        r = data.get("r%d" % i)
        if not r:
            continue
        text = next(((r.get("f%d" % j) or {}).get("text") for j in range(len(README_NAMES)) if (r.get("f%d" % j) or {}).get("text")), None)
        man = None
        for m in ("m0", "m1"):
            t = (r.get(m) or {}).get("text")
            if t:
                try:
                    man = A.manifest(json.loads(t))
                    break
                except ValueError:
                    pass
        out[k] = {"readme": A.analyze(text) if text else {"features": {}, "os": {}, "none": True}, "manifest": man,
                  "readmeLure": A.lure_signals(text) if text else [], "shots": A.readme_shots(text, full_names.get(k) or k) if text else []}
    return out


def gitlab_status(k, prev):
    path = k[len("gitlab.com/"):]
    base = "%s/projects/%s" % (GITLAB_API, urllib.parse.quote(path, safe=""))
    raw = http_get(base)
    if raw is None:
        return {"notFound": True}
    d = json.loads(raw)
    e = {"repo": {"pushed": d.get("last_activity_at"), "stars": d.get("star_count"), "archived": bool(d.get("archived")),
                  "full": d.get("path_with_namespace"), "desc": d.get("description") or ""}}
    rel = json.loads(http_get(base + "/releases?per_page=1") or b"[]")
    if rel:
        r = rel[0]
        e["release"] = {"tag": r.get("tag_name"), "date": r.get("released_at") or r.get("created_at"),
                        "pre": bool(r.get("upcoming_release")), "url": (d.get("web_url") or "") + "/-/releases"}
        e["assetOs"] = A.os_from_assets([l.get("name") or l.get("url") or "" for l in ((r.get("assets") or {}).get("links") or [])])
    else:
        e["noRelease"] = True
    if (prev.get("repo") or {}).get("pushed") == e["repo"]["pushed"] and "readme" in prev:
        e["readme"], e["manifest"] = prev.get("readme"), prev.get("manifest")
    else:
        text, branch = None, urllib.parse.quote(d.get("default_branch") or "main", safe="")
        for f in README_NAMES:
            t = http_get("%s/repository/files/%s/raw?ref=%s" % (base, urllib.parse.quote(f, safe=""), branch))
            if t:
                text = t.decode("utf-8", "replace")
                break
        e["readme"], e["manifest"] = (A.analyze(text) if text else {"features": {}, "os": {}, "none": True}), None
    return e


def refresh_status(projects):
    token = (os.environ.get("PW_GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    path = os.path.join(DATA, "status.json")
    data = load_json(path, {"format": "port-watch-status", "version": 1, "repos": {}})
    repos = data.setdefault("repos", {})
    keys = sorted({p["k"] for p in projects if p.get("k") and "/" in p["k"] and not p["k"].startswith("itch.io/")})
    gh_keys = [k for k in keys if not k.startswith("gitlab.com/")]
    gl_keys = [k for k in keys if k.startswith("gitlab.com/")]
    if not token:
        log("  No GitHub token available; skipping GitHub projects")
        gh_keys = []
    fresh, changed = {}, []
    for i in range(0, len(gh_keys), 40):
        batch = gh_keys[i:i + 40]
        try:
            res = meta_batch(batch, token)
        except Exception as e:
            log("  GitHub batch %d failed (%s); keeping previous results for it" % (i // 40 + 1, e))
            continue
        for k, e in res.items():
            prev = repos.get(k) or {}
            fresh[k] = e
            if e.get("notFound"):
                continue
            if (prev.get("repo") or {}).get("pushed") != e["repo"]["pushed"] or "readme" not in prev or "readmeLure" not in prev or "shots" not in prev:
                changed.append(k)             # new, pushed since last run, or read before lure signals/screenshots existed
            else:
                e["readme"], e["manifest"], e["readmeLure"], e["shots"] = prev.get("readme"), prev.get("manifest"), prev.get("readmeLure"), prev.get("shots")
        time.sleep(0.5)
    log("  GitHub: %d of %d repos read, %d need their README read" % (len(fresh), len(gh_keys), len(changed)))
    for i in range(0, len(changed), 15):
        batch = changed[i:i + 15]
        try:
            res = readme_batch(batch, token, {k: (fresh.get(k, {}).get("repo") or {}).get("full") or k for k in batch})
        except Exception as e:
            log("  README batch failed (%s); keeping previous README results" % e)
            res = {}
        for k in batch:
            if k in res:
                fresh[k].update(res[k])
            else:
                prev = repos.get(k) or {}
                if "readme" in prev:
                    fresh[k]["readme"], fresh[k]["manifest"] = prev.get("readme"), prev.get("manifest")
                    if "readmeLure" in prev:
                        fresh[k]["readmeLure"] = prev["readmeLure"]
                    if "shots" in prev:
                        fresh[k]["shots"] = prev["shots"]
        time.sleep(0.5)
    for k in gl_keys:
        try:
            fresh[k] = gitlab_status(k, repos.get(k) or {})
        except Exception as e:
            log("  %s: GitLab couldn't be read (%s); keeping the previous result" % (k, e))
    for k, e in fresh.items():
        repos[k] = {x: v for x, v in e.items() if v is not None}
    tracked = set(keys)
    for k in [k for k in repos if k not in tracked]:
        del repos[k]                      # no longer tracked
    log("  %d projects in status.json (%d not found)" % (len(repos), sum(1 for e in repos.values() if e.get("notFound"))))
    data["generated"] = NOW
    return write_json_if_changed(path, data)


# ---------------------------------------------------------------- IGDB screenshots
TWITCH_TOKEN_URL = os.environ.get("PW_TWITCH_TOKEN_URL", "https://id.twitch.tv/oauth2/token")
IGDB_URL = os.environ.get("PW_IGDB_URL", "https://api.igdb.com/v4")
IGDB_PLATFORMS = {"PC": 6, "Xbox One": 49, "Xbox 360": 12, "XBLA (Xbox 360)": 12, "Xbox (original)": 11, "PS1": 7, "PS2": 8, "PS3": 9, "PS4": 48, "PSP": 38,
                  "PS Vita": 46, "GameCube": 21, "Wii": 5, "Wii U": 41, "Switch": 130, "N64": 4, "SNES": 19, "NES": 18, "Mega Drive": 29, "32X": 30,
                  "Saturn": 32, "Dreamcast": 23, "Master System": 64, "Game Gear": 35, "GBA": 24, "Game Boy": 33, "Game Boy Color": 22, "DS": 20,
                  "3DS": 37, "Virtual Boy": 87, "Arcade": 52, "Sega CD": 78, "Mobile": "39,34"}
MAX_IGDB = int(os.environ.get("PW_MAX_IGDB", "700"))
IGDB_EROTIC_THEME = 42   # IGDB's "Erotic" theme; such games are blurred by default on the page

def igdb_token(cid, secret):
    body = urllib.parse.urlencode({"client_id": cid, "client_secret": secret, "grant_type": "client_credentials"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TWITCH_TOKEN_URL, data=body, headers={"User-Agent": UA}), timeout=30) as r:
        return json.loads(r.read())["access_token"]

def igdb_query(cid, token, body):
    req = urllib.request.Request(IGDB_URL + "/games", data=body.encode(), headers={"Client-ID": cid, "Authorization": "Bearer " + token,
                                 "Accept": "application/json", "User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            raise

def igdb_match(title, results):
    q, best = norm(title), None
    for g in results or []:
        n = norm(g.get("name", ""))
        score = 1.0 if n == q else difflib.SequenceMatcher(None, q, n).ratio()
        if numbers(q) != numbers(n):
            score -= 0.3
        if best is None or score > best[0]:
            best = (score, g)
    return best if best and best[0] >= 0.85 else None

def refresh_screens(projects, overrides):
    cid, secret = os.environ.get("IGDB_CLIENT_ID", "").strip(), os.environ.get("IGDB_CLIENT_SECRET", "").strip()
    path = os.path.join(DATA, "screens.json")
    data = load_json(path, {"format": "port-watch-screens", "version": 1, "games": {}, "map": {}})
    games, mapping = data.setdefault("games", {}), data.setdefault("map", {})
    if not cid or not secret:
        log("  IGDB_CLIENT_ID / IGDB_CLIENT_SECRET aren't set; skipping IGDB screenshots")
        return False
    try:
        token = igdb_token(cid, secret)
    except Exception as e:
        log(f"  Twitch sign-in failed ({e}); skipping IGDB screenshots")
        return False
    wanted = {}
    for p in projects:
        key = p.get("k") or p["id"]
        fix = overrides.get(key) or overrides.get(p["id"]) or {}
        if fix.get("hide"):
            continue
        title = cover_title(fix.get("title") or p.get("g", ""))
        plat = fix.get("platform") or p.get("p") or ""
        pid = IGDB_PLATFORMS.get(plat)
        if not title or not pid:
            continue
        q = f"{norm(title)}|{pid}"
        mapping[key] = q
        wanted.setdefault(q, (title, pid, plat))
    for k in [k for k in mapping if k not in {p.get("k") or p["id"] for p in projects}]:
        del mapping[k]
    now = datetime.datetime.now(datetime.timezone.utc)
    todo = []
    for q, (title, pid, plat) in wanted.items():
        g = games.get(q)
        if g and g.get("rev") != 2 and len(g.get("shots") or []) < 3:
            todo.append((q, title, pid, plat))   # missed or thin under the older rules: look it up once more
            continue
        if g and g.get("id") and "nsfw" not in g:
            todo.append((q, title, pid, plat))   # found before the theme check existed: look it up once more
            continue
        if g and (g.get("shots") or (now - datetime.datetime.fromisoformat(g.get("checked", "2000-01-01T00:00:00Z").replace("Z", "+00:00"))).days < 30):
            continue                  # found before, or missed less than 30 days ago
        todo.append((q, title, pid, plat))
    log(f"  {len(todo)} games to look up on IGDB (max {MAX_IGDB} this run)")
    found = topped = 0
    for q, title, pid, plat in todo[:MAX_IGDB]:
        safe = bare_title(title).replace('"', "").replace("\\", "")
        try:
            res = igdb_query(cid, token, f'search "{safe}"; fields name,first_release_date,screenshots.image_id,themes; where platforms = ({pid}); limit 10;')
        except Exception as e:
            log(f"  {title}: IGDB error ({e})")
            time.sleep(0.3)
            continue
        time.sleep(0.3)                # IGDB allows 4 requests a second
        m = pick_match(title, res, lambda g: g.get("name"), lambda g: ts_year(g.get("first_release_date")), plat)
        if m:
            score, g = m
            shots = [x["image_id"] for x in (g.get("screenshots") or []) if x.get("image_id")][:8]
            entry = {"name": g.get("name"), "id": g.get("id"), "shots": shots, "match": round(score, 3), "checked": NOW, "rev": 2,
                     "nsfw": IGDB_EROTIC_THEME in (g.get("themes") or [])}
            if len(shots) < 3:
                # thin results: add screenshots from the same game's other platform versions
                n0 = len(shots)
                try:
                    more = igdb_query(cid, token, f'search "{safe}"; fields name,first_release_date,screenshots.image_id; limit 12;')
                    time.sleep(0.3)
                    year = ts_year(g.get("first_release_date"))
                    for o in more or []:
                        if o.get("id") == g.get("id") or not pick_match(title, [o], lambda x: x.get("name"), lambda x: None, "", 0.95):
                            continue
                        oy = ts_year(o.get("first_release_date"))
                        if year and oy and abs(oy - year) > 1:
                            continue      # a different game that shares the name
                        for x in o.get("screenshots") or []:
                            if x.get("image_id") and x["image_id"] not in shots and len(shots) < 8:
                                shots.append(x["image_id"])
                except Exception as e:
                    log(f"  {title}: IGDB error while adding other versions ({e})")
                entry["shots"] = shots
                if len(shots) > n0:
                    entry["more"] = len(shots) - n0
                    topped += 1
            games[q] = entry
            found += bool(entry["shots"])
        else:
            games[q] = {"shots": [], "checked": NOW, "rev": 2}
    used = set(mapping.values())
    for q in [q for q in games if q not in used]:
        del games[q]
    log(f"  IGDB: screenshots found for {found} of {min(len(todo), MAX_IGDB)} looked up ({topped} topped up from other versions)")
    data["generated"] = NOW
    return write_json_if_changed(path, data)

# ---------------------------------------------------------------- libretro-thumbnails (box art, in-game shot, title screen)
LT_REPOS = {"N64": "Nintendo_-_Nintendo_64", "SNES": "Nintendo_-_Super_Nintendo_Entertainment_System", "NES": "Nintendo_-_Nintendo_Entertainment_System",
            "Game Boy": "Nintendo_-_Game_Boy", "Game Boy Color": "Nintendo_-_Game_Boy_Color", "GBA": "Nintendo_-_Game_Boy_Advance", "DS": "Nintendo_-_Nintendo_DS",
            "3DS": "Nintendo_-_Nintendo_3DS", "GameCube": "Nintendo_-_GameCube", "Wii": "Nintendo_-_Wii", "Wii U": "Nintendo_-_Wii_U", "Virtual Boy": "Nintendo_-_Virtual_Boy",
            "PS1": "Sony_-_PlayStation", "PS2": "Sony_-_PlayStation_2", "PS3": "Sony_-_PlayStation_3", "PSP": "Sony_-_PlayStation_Portable", "PS4": "Sony_-_PlayStation_4",
            "Xbox (original)": "Microsoft_-_Xbox", "Xbox 360": "Microsoft_-_Xbox_360", "XBLA (Xbox 360)": "Microsoft_-_Xbox_360", "Mega Drive": "Sega_-_Mega_Drive_-_Genesis",
            "32X": "Sega_-_32X", "Saturn": "Sega_-_Saturn", "Dreamcast": "Sega_-_Dreamcast", "Master System": "Sega_-_Master_System_-_Mark_III", "Game Gear": "Sega_-_Game_Gear"}
LT_BAD = re.compile(r"\((?:[^)]*\b(beta|proto|prototype|demo|sample|kiosk|promo|unl|pirate|hack|aftermarket|program|debug|competition|preview|trial)\b[^)]*)\)", re.I)
API = os.environ.get("PW_GH_API", "https://api.github.com")

def lt_region_rank(base):
    tags = " ".join(re.findall(r"\(([^)]*)\)", base))
    r = 0 if re.search(r"\bUSA\b", tags) else 1 if re.search(r"\bWorld\b", tags) else 2 if re.search(r"\bEurope\b", tags) else 3 if re.search(r"\bJapan\b", tags) else 4
    return r + (0.3 if re.search(r"\bRev\b", tags) else 0) + (0.5 if re.search(r"Disc [2-9]", tags) else 0)

def lt_index(names):
    out = []
    for n in names:
        if not n.lower().endswith(".png") or LT_BAD.search(n):
            continue
        base = n[:-4]; tp = base.split(" (")[0]
        segs = []
        for sg in tp.split(" - "):
            m = re.match(r"^(.*), (The|A|An)$", sg)
            segs.append(f"{m.group(2)} {m.group(1)}" if m else sg)
        out.append((n, vnorm(" ".join(segs)), vnorm(" ".join(segs[1:])) if len(segs) > 1 else "", lt_region_rank(base), len(base)))
    return out

def lt_match(idx, title):
    tries = [cover_title(bare_title(title))]
    if re.search(r"\s(64|1)$", tries[0]):
        tries.append(re.sub(r"\s(64|1)$", "", tries[0]))
    for t in tries:
        q = vnorm(t)
        if not q:
            continue
        best = None
        for n, full, alt, rr, ln in idx:
            for cand in (full, alt):
                if not cand:
                    continue
                if cand.replace(" ", "") == q.replace(" ", ""):
                    sc = 1.0
                else:
                    if abs(len(cand) - len(q)) > max(6, len(q) * 0.35):
                        continue
                    sc = difflib.SequenceMatcher(None, q, cand).ratio()
                    if sc < 0.9 or numbers(q) != numbers(cand):
                        continue
                key = (-sc, rr, ln)
                if best is None or key < best[0]:
                    best = (key, n)
        if best:
            return best[1]
    return None

def lt_lists(repo, token):
    br = "main" if repo == "Sega_-_Naomi_2" else "master"
    hdr = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}
    top = json.loads(http_get(f"{API}/repos/libretro-thumbnails/{repo}/contents/?ref={br}", hdr) or b"[]")
    out = {}
    for d in top:
        if d.get("name") in ("Named_Boxarts", "Named_Snaps", "Named_Titles") and d.get("sha"):
            tree = json.loads(http_get(f"{API}/repos/libretro-thumbnails/{repo}/git/trees/{d['sha']}", hdr) or b"{}")
            out[d["name"]] = {e["path"] for e in tree.get("tree", []) if e.get("type") == "blob"}
    return out

def refresh_libretro(projects, overrides):
    token = (os.environ.get("PW_GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    path = os.path.join(DATA, "libretro.json")
    data = load_json(path, {"format": "port-watch-libretro", "version": 1, "map": {}})
    mp = data.setdefault("map", {})
    if not token:
        log("  No GitHub token available; skipping libretro matching")
        return False
    now = datetime.datetime.now(datetime.timezone.utc)
    wanted = {}
    for p in projects:
        key = p.get("k") or p["id"]
        fix = overrides.get(key) or overrides.get(p.get("id", "")) or {}
        if fix.get("hide"):
            continue
        plat = fix.get("platform") or p.get("p") or ""
        repo = LT_REPOS.get(plat)
        if not repo:
            continue
        title = fix.get("title") or p.get("g", "")
        cv = p.get("cv") if not fix.get("title") else ""
        wanted[key] = (repo, title, cv)
    for k in [k for k in mp if k not in wanted]:
        del mp[k]
    todo = {}
    for key, (repo, title, cv) in wanted.items():
        e = mp.get(key)
        if e and e.get("q") == norm(title) and (e.get("file") or (now - datetime.datetime.fromisoformat(e.get("checked", "2000-01-01T00:00:00Z").replace("Z", "+00:00"))).days < 30):
            continue
        todo.setdefault(repo, []).append((key, title, cv))
    log(f"  {sum(len(v) for v in todo.values())} games to match on libretro-thumbnails, across {len(todo)} consoles")
    hits = 0
    for repo, items in todo.items():
        try:
            lists = lt_lists(repo, token)
        except Exception as e:
            log(f"  {repo}: couldn't list libretro-thumbnails ({e}); keeping previous matches")
            continue
        idx = lt_index(sorted(lists.get("Named_Boxarts", set())))
        for key, title, cv in items:
            f = cv.split("|", 1)[1] if cv and "|" in cv else lt_match(idx, title)
            if f:
                mp[key] = {"repo": repo, "file": f, "snap": f in lists.get("Named_Snaps", set()), "title": f in lists.get("Named_Titles", set()),
                           "q": norm(title), "checked": NOW}
                hits += 1
            else:
                mp[key] = {"q": norm(title), "checked": NOW}
    log(f"  libretro-thumbnails: matched {hits}")
    data["generated"] = NOW
    return write_json_if_changed(path, data)

# ---------------------------------------------------------------- main
def main():
    seed = seed_projects()
    known = {p.get("k") for p in seed if p.get("k")}
    extra = [p for p in awesome_projects() if p["k"] not in known]
    log(f"Port Watch list: {len(seed)} built-in projects, {len(extra)} newer ones from Awesome Decomp Games")
    log("Covers:")
    overrides = load_overrides()
    if overrides:
        log(f"Shared fixes: {len(overrides)} projects in overrides.json")
    taken = known | {p["k"] for p in extra}
    added = [p for p in load_added() if p["k"] not in taken]
    if added:
        log(f"Shared added projects: {len(added)}")
    for p in added:                       # an added project's own cover link works like a pinned cover
        if p["cover"] and not (overrides.get(p["k"]) or {}).get("cover"):
            overrides = {**overrides, p["k"]: {**(overrides.get(p["k"]) or {}), "cover": p["cover"]}}
    extra = extra + added
    refresh_covers(with_games(seed + extra, overrides), overrides)
    log("itch.io devlogs:")
    refresh_itch(seed + added)
    log("libretro-thumbnails:")
    refresh_libretro(with_games(seed + extra, overrides), overrides)
    log("IGDB screenshots:")
    refresh_screens(with_games(seed + extra, overrides), overrides)
    log("Shared update checks:")
    refresh_status([p for p in seed + extra if not ((overrides.get(p.get("k") or "") or overrides.get(p["id"]) or {}).get("hide"))])

if __name__ == "__main__":
    main()
