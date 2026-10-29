# Repository notes

Layout (all in the root of the GitHub repo, next to your existing README/guides):

- `repository.kodigamelauncher/`  the repository addon users install once
- `metadata.games.igdb/`          IGDB + SteamGridDB scraper
- `service.gamelauncher/`         Play.avi launcher service (Windows)
- `generate.py`                   builds `zips/` (zips, addons.xml, addons.xml.md5)
- `zips/`                         generated; this is what Kodi downloads

## Releasing an update
1. Edit the addon and raise `version` in its `addon.xml`.
2. Run `python3 generate.py`.
3. Commit and push, including `zips/`.

## Installing in Kodi
Settings -> Add-ons -> Install from zip file ->
`zips/repository.kodigamelauncher/repository.kodigamelauncher-1.0.1.zip`.
Then Install from repository -> Kodi Game Launcher Repository -> install both addons.
