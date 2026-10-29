# Kodi Game Launcher

Turn Kodi into a console-style front end for your Windows PC games. Kodi shows your games with descriptions and artwork, and a small service launches the game when you press play.

## What's new in 3.0.0

**Playnite is no longer needed.** The IGDB + SteamGridDB scraper now fetches all game metadata and artwork straight into Kodi, so there is nothing to export. You also don't need AutoHotkey or a special MPV setup.

See the [changelog](CHANGELOG.md) for details.

## How it works

1. Each game gets a folder with a `Play.avi` file and a shortcut (`.lnk`) to the game.
2. The **IGDB + SteamGridDB Game Scraper** adds the game to your Kodi library with metadata and artwork.
3. When you play a game in Kodi, the **Game Launcher** service sees `Play.avi`, shows the game's fanart while it loads, and starts the shortcut.

Steam, Epic, GOG, emulators and standalone games all work, because the shortcut decides what runs.

## Requirements

- Windows
- Kodi 19 or newer
- A free [Twitch developer app](https://dev.twitch.tv/console) (for IGDB metadata)
- A free [SteamGridDB API key](https://www.steamgriddb.com/profile/preferences/api) (for artwork)

## Install

Download the repository addon and install it in Kodi with **Add-ons → Install from zip file**:

[repository.kodigamelauncher-1.0.1.zip](https://github.com/GoldStart5/Kodi-Game-Launcher/raw/main/zips/repository.kodigamelauncher/repository.kodigamelauncher-1.0.1.zip)

Then install both addons from the repository. Kodi will keep them updated. Full steps are in the [Installation Guide](Installation-Guide.md), and fixes for common problems are in [Troubleshooting](Troubleshooting.md).

## Tip

The optional Cinema Themes addon, included in the repository, plays theme music for your game pages. It needs a separate copy of `mpv.exe`.

## License

MIT
