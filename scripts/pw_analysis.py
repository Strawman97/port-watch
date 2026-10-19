"""Port Watch's detection rules, ported from index.html so the shared checks give the same answers as the page.

Keep this file in step with the JavaScript in index.html (FEATURES, NEG, OS_TEXT, BUILD_HEAD, BUILD_LINE,
ASSET_*, OS_TOKENS, TARGET_*, sentences, analyze, osFromAssets, consoleTargets, applyManifest).
Flags: re.I | re.A gives JavaScript's ASCII-only \\b and \\w.
"""
import re

F = re.I | re.A
NEG = re.compile(r"\b(not|no|without|planned|todo|missing|unsupported|isn'?t|aren'?t|won'?t|lacks?|future|coming soon|wishlist|roadmap|would like|eventually|broken|disabled|untested)\b", F)
FEATURES = [
    ("hfr", r"\b(60|90|120|144|165|240|360)\s?(fps|hz)\b|high(er)?[\s-](frame[\s-]?rate|refresh)|uncapped|unlocked (frame|fps)|fps unlock|frame[\s-]?rate (cap|limit|unlock)|refresh rate"),
    ("aspect", r"ultra-?wide|widescreen|21:9|32:9|16:10|aspect ratio"),
    ("hdr", r"\bhdr ?10\b|\bscrgb\b|\bhdr (output|display|support|mode|monitor|screen)|\btrue hdr\b|\bhdr\b(?! ?(rendering|render|lighting|bloom|tone|tonemap|effects?|pipeline|textures?))"),
    ("res", r"\b(4k|1440p|2160p|5k)\b|resolution scal|internal resolution|render(ing)? (scale|resolution)|supersampl|\b[234]x (internal )?resolution|high(er)? resolutions?|native resolution|\bhd\b"),
    ("dlss", r"\bdlss\b"),
    ("fsr", r"\bfsr\b|fidelityfx"),
    ("xess", r"\bxess\b"),
    ("fg", r"frame[\s-]?gen(eration)?\b|\bafmf\b"),
    ("rt", r"ray[\s-]?trac"),
    ("tex", r"texture (pack|replacement|mod)s?|hd textures?|replace(ment)? textures|texture replac"),
    ("mods", r"\bmod(s|ding| loader| support| manager)\b|lua script|thunderstore"),
    ("kbm", r"keyboard|\bmouse\b|\bkbm\b"),
    ("online", r"\bonline\b|multiplayer|\bco-?op\b|netplay"),
    ("gyro", r"\bgyro"),
    ("dlc", r"\bdlcs?\b|downloadable content|expansion pack"),
    ("aa", r"\b(msaa|smaa|fxaa|taa)\b|anti-?aliasing"),
]
FEATURES = [(i, re.compile(p, F)) for i, p in FEATURES]
OS_TEXT = [
    ("Windows", r"\bwindows\b|\bwin64\b|\.exe\b|direct3d|d3d1[12]|\bpc\b"),
    ("Linux", r"\blinux\b|appimage|flatpak"),
    ("macOS", r"\bmacos\b|\bmac os\b|apple silicon|\bmac\b"),
    ("Steam Deck", r"steam ?deck|steamos"),
    ("Android", r"\bandroid\b|\.apk\b"),
    ("iOS", r"\bios\b|\bipados\b|\biphone\b|\bipad\b"),
]
OS_TEXT = [(i, re.compile(p, F)) for i, p in OS_TEXT]
BUILD_HEAD = re.compile(r"build|compil|from source|development|developer|contribut|requirements?|prerequisite|dependenc|what you need|toolchain|setup for dev|getting the source", F)
BUILD_LINE = re.compile(r"\b(build(ing|s|er)?|compil\w*|cmake|msvc|visual studio|xcode|devkit\w*|toolchain|wsl|homebrew|brew install|apt(-get)? install|pacman|vcpkg|python3?|\.bat\b|\.command\b|\.sh\b|terminal|command line|clone)\b", F)
ASSET_SKIP = re.compile(r"(^|[^a-z])(builder|build[-_ ]?tools?|patcher|tools?|sdk|source|src|symbols?|pdb|debug[-_ ]?info|checksums?|sha256|md5)([^a-z]|$)", F)
ASSET_EXT = [(re.compile(p, F), o) for p, o in [
    (r"\.(exe|msi)$", "Windows"), (r"\.(appimage|deb|rpm|flatpak(ref)?)$", "Linux"), (r"\.(dmg|pkg)$", "macOS"), (r"\.apk$", "Android"), (r"\.ipa$", "iOS"),
    (r"\.(3dsx|cia)$", "3DS"), (r"\.(nro|nsp|xci)$", "Switch"), (r"\.vpk$", "PS Vita"), (r"\.(wuhb|rpx)$", "Wii U"), (r"eboot\.pbp$|\.pbp$", "PSP")]]
OS_TOKENS = {"windows": "Windows", "win": "Windows", "win64": "Windows", "win32": "Windows", "winx64": "Windows", "msvc": "Windows", "pc": "Windows",
             "linux": "Linux", "appimage": "Linux", "flatpak": "Linux", "steamos": "Linux", "macos": "macOS", "mac": "macOS", "osx": "macOS", "darwin": "macOS",
             "universal2": "macOS", "android": "Android", "ios": "iOS", "iphone": "iOS", "ipad": "iOS", "ipados": "iOS", "3ds": "3DS", "n3ds": "3DS",
             "switch": "Switch", "vita": "PS Vita", "psvita": "PS Vita", "wiiu": "Wii U", "psp": "PSP", "steamdeck": "Steam Deck"}
TARGET_ALT = r"(?:nintendo\s+)?(?:new\s+)?(3ds|switch|ps ?vita|vita|wii ?u|psp)"
TARGET_RES = [re.compile(r"\b(?:ports?|ported|running|runs|playable|plays|native(?:ly)?|homebrew|installs?)\s+(?:natively\s+)?(?:to|for|on)\s+(?:the\s+|your\s+)?" + TARGET_ALT + r"\b", F),
              re.compile(r"\bnative\s+" + TARGET_ALT + r"\s+(?:port|version|build|homebrew)", F),
              re.compile(r"\b" + TARGET_ALT + r"\s+(?:port|homebrew)\b", F)]
RJ_SYS = {"Xbox 360": "Xbox 360", "Xbox": "Xbox (original)", "PS3": "PS3", "PS2": "PS2", "PSP": "PSP", "PS Vita": "PS Vita", "PS1": "PS1", "Wii U": "Wii U",
          "Wii": "Wii", "GameCube": "GameCube", "N64": "N64", "Switch": "Switch", "SNES": "SNES", "GBA": "GBA", "GBC": "Game Boy Color", "GB": "Game Boy",
          "NDS": "DS", "3DS": "3DS", "Virtual Boy": "Virtual Boy", "NES": "NES", "Master System": "Master System", "Game Gear": "Game Gear", "32X": "32X",
          "Saturn": "Saturn", "Dreamcast": "Dreamcast", "Genesis": "Mega Drive", "Arcade": "Arcade", "Sega CD": "Sega CD", "3DO": "3DO",
          "Atari Jaguar": "Atari Jaguar", "Neo Geo": "Neo Geo"}

CODE_BLOCK = re.compile(r"```[\s\S]*?```")
JS_SPACE = re.compile(r"[\s\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+")


def sentences(text):
    t = CODE_BLOCK.sub(" ", str(text or ""))
    t = re.sub(r"<[^>]+>", " ", t)
    out = []
    for s in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", t):
        s = re.sub(r"[#*_`>|\[\]]", " ", s)
        s = re.sub(r"\(https?:[^)]+\)", "", s)
        s = JS_SPACE.sub(" ", s).strip()
        if len(s) > 2:
            out.append(s)
    return out


def target_name(x):
    x = re.sub(r"\s+", "", x.lower())
    return {"3ds": "3DS", "switch": "Switch", "psvita": "PS Vita", "vita": "PS Vita", "wiiu": "Wii U", "psp": "PSP"}.get(x)


def console_targets(text):
    out = {}
    for line in sentences(text):
        for r in TARGET_RES:
            m = r.search(line)
            if m:
                t = target_name(m.group(1))
                if t:
                    out[t] = True
    return out


def analyze(text):
    out = {"features": {}, "os": {}, "targets": {}, "v": 2}
    kept, skip = [], 0
    for raw in re.split(r"\r?\n", CODE_BLOCK.sub(" ", str(text or ""))):
        h = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", raw)
        if h:
            lvl = len(h.group(1))
            if skip and lvl <= skip:
                skip = 0
            if not skip and BUILD_HEAD.search(h.group(2)):
                skip = lvl
            continue
        if not skip:
            kept.append(raw)
    for line in sentences(text):
        neg = bool(NEG.search(line))
        for fid, r in FEATURES:
            if r.search(line):
                if not neg:
                    out["features"][fid] = "yes"
                elif fid not in out["features"]:
                    out["features"][fid] = "planned"
    for line in sentences("\n".join(kept)):
        if NEG.search(line) or BUILD_LINE.search(line):
            continue
        for oid, r in OS_TEXT:
            if r.search(line):
                out["os"][oid] = True
    out["targets"] = console_targets("\n".join(kept))
    return out


def name_tokens(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s or ""))
    s = re.sub(r"([A-Za-z])(\d)(?!ds)", r"\1 \2", s)
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def os_from_assets(names):
    s = {}
    for n in names:
        if ASSET_SKIP.search(re.sub(r"\.[a-z0-9]+$", "", n, flags=F)):
            continue
        hit = False
        for r, o in ASSET_EXT:
            if r.search(n):
                s[o] = True
                hit = True
        if hit:
            continue
        for t in name_tokens(re.sub(r"\.(zip|7z|tar\.gz|tgz|tar\.xz|xz|gz)$", "", n, flags=F)):
            if t in OS_TOKENS and OS_TOKENS[t] != "Steam Deck":
                s[OS_TOKENS[t]] = True
    return s


def manifest(j):
    if not isinstance(j, dict):
        return None
    sys_ = j.get("system")
    sys_ = sys_[0] if isinstance(sys_, list) and sys_ else sys_
    types = j.get("type") if isinstance(j.get("type"), list) else ([j["type"]] if j.get("type") else [])
    targets = j.get("targets") if isinstance(j.get("targets"), list) else ([j["targets"]] if j.get("targets") else [])
    return {"game": j["game"][:120] if isinstance(j.get("game"), str) else "",
            "system": RJ_SYS.get(sys_) or (str(sys_)[:30] if sys_ else ""),
            "type": "Recompilation" if "recomp" in types else ("Decompilation" if ("port" in types or "decomp" in types) else ""),
            "targets": [str(t) for t in targets][:8],
            "notes": j["notes"][:600] if isinstance(j.get("notes"), str) else "",
            "approach": j["approach"][:200] if isinstance(j.get("approach"), str) else ""}


# Malware-lure README signals (kept in step with LURE_RE in index.html). The page combines these with the
# repository's size, language, age, stars and name to decide whether a project looks like a lure.
LURE_RE = {
    "badges": re.compile(r"img\.shields\.io/badge/(downloads?|rating|users|installs|active[-_%20 ]*users)[-_%]", F),
    "dlbutton": re.compile(r"badge/download[^)\s\"']*(windows|mac|now|latest|for)|\bdownload (for windows|for mac|now|the latest version)\b", F),
    "filehost": re.compile(r"(mediafire\.com|mega\.nz|gofile\.io|pixeldrain\.com|anonfiles|dropbox\.com/s|bit\.ly/|tinyurl\.com|cutt\.ly|t\.me/|discord(app)?\.com/attachments|qiwi\.gg|krakenfiles|sendspace)", F),
    "offsite": re.compile(r"\]\(https?://[a-z0-9-]+\.github\.io/[^)\s]*(download|setup|install)[^)\s]*\)|download (for )?(windows|mac(os)?)[^\n]{0,200}?\]\(https?://(?!github\.com/|img\.shields\.io/)[^)\s]+\)", F),
    "password": re.compile(r"(archive|zip|rar|7z|extract)[^\n]{0,60}password|password[^\n]{0,25}[:=]\s*\S{2,}", F),
}


def lure_signals(text):
    return [k for k, r in LURE_RE.items() if r.search(text or "")]
