# Port Watch

A single-page tracker for native PC (and handheld) ports of console games, made through static recompilation, decompilation, reimplementation or compatibility layers. Follow the projects you care about, see what each one supports, and get told when they release something new.

**Live site:** https://strawman97.github.io/port-watch/

> Port Watch links to code projects only. It does not host, link to or include game files, ROMs or disc images. Every project it lists needs your own legally obtained copy of the game.

## What it does

- **Tracks 500+ projects** across Xbox 360, Xbox, PS1–PS4, N64, GameCube, Wii, Wii U, SNES, GBA, DS, 3DS and more.
- **Shows what each port offers:**
  - Type (recompilation, decompilation, source port, reimplementation or compatibility layer) and original platform, including PC for games that began there.
  - What it runs on: Windows, Linux, macOS, Steam Deck, Android, iOS, Switch, 3DS, PS Vita, Wii U and PSP.
  - Features: high refresh rate, aspect ratios, HDR, higher resolution, DLSS, FSR, XeSS, frame generation, ray tracing, texture packs, mods, keyboard and mouse, online play, gyro aiming, anti-aliasing and DLC support.
  - Last updated date, latest release, whether it's playable (has a public release), and whether the game was ever released on PC.
- **List and grid views,** with box art from libretro-thumbnails and other sources. Games with several projects (The Darkness, Forza Horizon, Banjo-Kazooie and so on) are grouped into one entry, with a tab for each repository showing its own features, platforms and releases. **Group by game** turns this off.
- **Screenshots:** each project shows screenshots from its own README (the port itself), IGDB and libretro-thumbnails. Click one to enlarge it.
- **Malware-lure warnings:** repositories that look like malware disguised as game ports are flagged and hidden (see below).
- **Follow list:** tap the heart on a project, then use **Check followed** to check only those.
- **Alerts** for new releases, newly listed projects and repositories that disappear.
- **Find a game:** search the unbaked.games registry to see whether a recompilation or decompilation exists for a game, and add any project to your list in one click.
- **Add project:** track anything else by its GitHub, GitLab or itch.io link.

## Getting started

1. Open the site. It starts with a built-in list and doesn't check anything until you ask.
2. Follow the projects you're interested in with the heart.
3. Click **Check for updates**, or **Check followed** to refresh just those. Both use Port Watch's shared data (see below), so no GitHub account or token is needed.

Everything you do (follows, notes, edits, settings) is saved in your own browser. Use **Settings > Export backup** to keep a copy or move it to another browser.

### Adding a GitHub token (optional)

You only need a token for projects you added yourself, for **Check this project now**, or if the shared data is ever unavailable. Without one, GitHub allows 60 requests an hour.

1. On GitHub, go to **Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token**.
2. Give it a name and an expiry date. Under **Repository access**, choose **Public repositories (read-only)**. No other permissions are needed.
3. Copy the token and paste it into **Settings > GitHub token** in Port Watch.

The token is stored only in your browser and is sent only to `api.github.com`. It is never included in backups.

### Shared data refreshed by this repository

Some sources can't be read from a web page, so a scheduled GitHub Actions workflow in this repository fetches them every three hours and saves the results in `data/`. Every visitor gets them automatically.

- **`data/covers.json`:** SteamGridDB covers for games without libretro box art.
- **`data/itch.json`:** the latest devlog posts of projects hosted on itch.io, such as Azimuth.
- **`data/status.json`:** every tracked GitHub and GitLab project's latest release, last activity, what its release files run on, and the features and platforms in its README and `.recomp.json`.

**Check for updates** and **Check followed** apply `status.json` first, then check directly only the projects it doesn't cover. That means projects you added yourself, plus itch.io devlogs when the shared copy is missing. Release alerts work exactly as before. The status line shows how long ago the shared data was refreshed.

Each project's details show where its cover came from, and for itch.io projects, whether the devlog was read and by which route. **Check this project now** re-checks a single project immediately.

If the shared itch.io copy is ever missing, **Settings > Read itch.io devlogs through a relay** is a backup. It asks rss2json.com, or allorigins.win if that fails. Both are free third-party relays and will see which itch.io feeds you read.

### Your own cover art

- **One game:** open the project, click **Find on SteamGridDB**, copy the cover's image link and paste it into **Cover image link**. Your own links always take priority.
- **In bulk, for the downloadable copy:** use **Settings > Export games needing covers**, run `scripts/sgdb_covers.py` with your own SteamGridDB API key, then **Import covers**:

  ```bash
  python3 scripts/sgdb_covers.py port-watch-needs-covers.json --key YOUR_SGDB_KEY
  ```

## Screenshots

Each project's details show up to ten screenshots, in this order:

1. **The project's README:** images of the port itself, so you see its widescreen, HDR or new renderer. Badges, logos, box art and banners are filtered out, and suspected malware lures never show their README images.
2. **IGDB:** screenshots of the original game, mainly for newer consoles. The workflow looks each game up on its original platform and only accepts a confident title match.
3. **libretro-thumbnails:** an in-game shot and the title screen, for games whose box art comes from libretro.

If a screenshot is wrong, open it and click **Hide this screenshot**. **Export fixes for everyone** shares hidden screenshots as `hideScreens` in `overrides.json`. Pinned screenshot links can be added there as `screens`.

## Malware-lure detection

Fake "PC port" repositories are a known way of spreading malware. Port Watch checks every repository for the warning signs they share:

- almost no content and no code;
- badges claiming download counts, user numbers or ratings;
- download links that leave GitHub, often to another account's GitHub Pages (buttons pointing at the project's own GitHub releases are fine);
- links to file hosts or link shorteners;
- password-protected downloads;
- a name copying a well-known project from a different owner, with few stars;
- a brand-new repository with almost no stars.

A repository with real code counts against a flag, so genuine projects with download buttons aren't flagged. Strong combinations mark a project as **Possible malware**. It's hidden from the list unless you tick **Show suspected malware lures**, and its details explain why. Weaker signs show a **Check before downloading** badge. **Add project** warns before you add a flagged repository.

**Export fixes for everyone** never includes suspected lures, hidden projects or deleted repositories, so they can't be shared by accident.

These are warning signs, not proof. Never run downloads from a project you're unsure about, and report suspicious repositories to GitHub.

## Deleted and archived repositories

Projects whose repository was deleted, made private or archived are left out of the list. Tick **Show deleted or archived** to see them; some archived projects still have working downloads.

## Privacy

Port Watch has no server, accounts or analytics. Your data never leaves your browser except for these requests, which only fetch public information:

| Destination | Why |
| --- | --- |
| `api.github.com`, `gitlab.com` | Releases, READMEs and activity for tracked projects (on checks) |
| `raw.githubusercontent.com` | This repository's shared data, the Awesome Decomp Games list, `.recomp.json` files and libretro box art |
| `cdn2.steamgriddb.com` | Cover images from SteamGridDB |
| `images.igdb.com` | Screenshots from IGDB |
| The hosts of README images (mostly GitHub) | Screenshots from projects' READMEs, only when you open a project |
| `unbaked.games` | The **Find a game** search |
| `en.wikipedia.org`, `upload.wikimedia.org` | Fallback cover art |
| `fonts.googleapis.com`, `fonts.gstatic.com` | Fonts |
| `api.rss2json.com`, `api.allorigins.win` | itch.io devlogs, only if you turn on the relay and the shared copy is missing |

## Data sources and credits

Port Watch builds on the work of these projects and lists. Their data and images belong to their respective owners; check each source's terms and licence before reusing it.

- [Awesome Decomp Games](https://github.com/SubmitGame/awesome-decomp-games): project list, release dates and activity
- [unbaked.games](https://unbaked.games): the registry behind **Find a game**
- [libretro-thumbnails](https://github.com/libretro-thumbnails): box art
- [SteamGridDB](https://www.steamgriddb.com): cover art, made by its community
- [IGDB](https://www.igdb.com): game screenshots
- [PortsDR](https://portsdr.com), [Recompendium](https://nio03.github.io/unricopie/en/) and [Read Only Memo](https://readonlymemo.com/decompilation-projects-and-n64-recompiled-list/): used to compile the original built-in list
- Every project developer whose work is tracked here

All game titles, trademarks and box art belong to their respective owners. Port Watch is an unofficial fan project and isn't affiliated with any game publisher, platform holder or listed project.

## Known limitations

- **Platforms and features are detected automatically** from release files, repository names, descriptions and READMEs, so some will be wrong or missing. Each project has a manual override for its title, platforms and PC release status.
- **"Playable" only means a public release exists.** It doesn't promise the game can be finished.
- **Data that lives in the page can lag.** Releases and new projects refresh from the Awesome Decomp Games list on each full check, but descriptions and PC release status stay as they were when the page was last updated.

## Maintaining the site

| Path | What it is |
| --- | --- |
| `index.html` | The whole site, served by GitHub Pages from the `main` branch |
| `scripts/refresh_data.py` | Fetches SteamGridDB covers, itch.io devlogs and every project's status (standard library only) |
| `scripts/pw_analysis.py` | The page's README, release-file, `.recomp.json`, malware-lure and README-screenshot rules, ported to Python |
| `.github/workflows/refresh-data.yml` | Runs the script every three hours and after `overrides.json` or `index.html` changes, and commits `data/` when it changes |
| `data/` | Written by the workflow; don't edit by hand |
| `scripts/sgdb_covers.py` | Optional helper for adding covers to a downloaded copy |

**Updating the page:** save the new version as `index.html`, then choose **Add file > Upload files** in this repository, describe the change and click **Commit changes**. GitHub Pages republishes within a minute or two; a hard refresh (Ctrl+Shift+R) shows it straight away.

**The SteamGridDB key** is stored as the repository secret `SGDB_API_KEY` (**Settings > Secrets and variables > Actions**). It's never written into files or logs. The status checks use the workflow's own `GITHUB_TOKEN`, which needs no setup. If GitHub ever limits it, add a read-only fine-grained token as the secret `PW_GH_TOKEN`.

**Fixing a project for everyone:** `overrides.json` in the repository root holds shared fixes. Every visitor's Port Watch and the refresh workflow read it. The simplest way to update it:

1. In Port Watch, correct the project as usual. Edit its game title, paste a cover image link, or change its platform, type, PC release or what it runs on.
2. Open **Settings > Export fixes for everyone**. This downloads a complete `overrides.json`: the current shared fixes plus your own. Check it doesn't include personal edits you'd rather keep to yourself.
3. Upload it to the repository, replacing the old file. Visitors see the fixes on their next visit. A corrected title gets a fresh SteamGridDB cover on the next workflow run, and a pasted cover link is used straight away.

Each entry is keyed by the project's repository (for example `speedbreakerproject/speedbreaker`) and can contain:

| Field | What it does |
| --- | --- |
| `title` | The game's name. A year in brackets, such as `(2005)`, is kept and helps the cover lookup pick the right game. |
| `cover` | A cover image link. It's used instead of any looked-up cover. |
| `platform` | The original platform, written as in Port Watch's filters, such as `Xbox 360`, or `PC` for games that began on PC. |
| `type` | `Recompilation`, `Decompilation`, `Source Port`, `Reimplementation` or `Compatibility layer`. **Source Port** is a game's own code brought to modern systems (DevilutionX for Diablo); **Reimplementation** is a new engine written from scratch (SiegeFX for Dungeon Siege). |
| `pcRelease` | One of the **PC release** values shown in Port Watch's filters. |
| `runsOn` | A list such as `["Windows", "Linux"]`, replacing the detected platforms. |
| `hide` | `true` removes the project from Port Watch entirely, for entries that don't belong. |
| `note` | Optional text shown in the project's details. |

A visitor's own edits in their browser still take priority for them.

**Adding a project for everyone:** add it in Port Watch with **Add project**, or with **Add** in **Find a game**, then use **Export fixes for everyone** and upload the file as above. Pasting a GitHub or GitLab link into **Add project** checks the repository straight away. It confirms the repository exists and isn't already tracked, fills in the title, platform and type, and shows its latest release, platforms and features, so you can correct anything before adding. Added projects go in the file's `added` section, keyed by repository:

```json
"added": {
  "k0nl/b2recomp": {
    "link": "https://github.com/K0NL/B2recomp",
    "title": "Bayonetta 2",
    "platform": "Switch",
    "type": "Recompilation",
    "pcRelease": "Never released on PC"
  }
}
```

`runsOn`, `cover`, `description` and `note` work here too. The file holds only your decisions. Releases, features and platforms come from `data/status.json`, which the workflow refreshes, so they never go stale. Visitors see an added project like any other, can follow it, and get a "new project" alert the first time it appears. The refresh workflow checks its releases, README and cover like a built-in project. Links that aren't on GitHub, GitLab or itch.io (keyed as `link:` plus the URL) are shown but can't be checked automatically. If Awesome Decomp Games later lists the same repository, Port Watch shows it only once.

**IGDB screenshots** need a Twitch developer app. Register one at dev.twitch.tv/console/apps with:

- **Name:** any unique name.
- **OAuth Redirect URL:** `https://localhost` (required by the form but never used).
- **Category:** Website Integration.
- **Client type:** Confidential.

Then store its client ID and a new secret as the repository secrets `IGDB_CLIENT_ID` and `IGDB_CLIENT_SECRET`. Without them, the workflow skips IGDB and the other screenshot sources still work.

**Changing detection rules:** the features, platforms and release-file rules exist twice, in the JavaScript in `index.html` and in `scripts/pw_analysis.py`. Change both together, or the shared data and in-page checks will disagree.

**When refreshes run:** every three hours, and also a few minutes after `overrides.json` or `index.html` is updated, so newly shared projects and fixes are checked straight away. To run one by hand, open **Actions > Refresh data > Run workflow**.

**If scheduled refreshes stop:** GitHub pauses scheduled workflows in public repositories after 60 days without activity. Re-enable it from the **Actions** tab.

If this repository is renamed or moved, update `DATA_REPO` near the top of the script in `index.html`. It tells the page where to fetch `data/` from.

Never commit API keys or tokens to this repository.

## Suggesting a project or a fix

Open an issue with the project's link, the game and its original platform, or describe what's wrong with an existing entry.

## Licence

Port Watch's own code (`index.html` and the scripts in `scripts/`) is released under the [MIT Licence](LICENSE).

The licence doesn't cover the third-party data and images the site displays, such as project lists, descriptions, box art and covers. Those belong to their respective owners and sources, listed under [Data sources and credits](#data-sources-and-credits).
