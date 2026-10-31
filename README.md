<div align="center">

<img src="repository.kodigamelauncher/icon.png" width="140" alt="Kodi Game Launcher logo">

# Kodi Game Launcher

**Turn Kodi into a console-style front end for your PC games.**
Browse your library with descriptions and artwork, press play, and the game starts.

[![Kodi 19+](https://img.shields.io/badge/Kodi-19%2B-1f6feb?style=flat-square)](https://kodi.tv)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078d4?style=flat-square)](#-requirements)
[![License: MIT](https://img.shields.io/badge/License-MIT-f5c518?style=flat-square)](LICENSE)

[**Install**](#-install) &nbsp;·&nbsp; [**How it works**](#-how-it-works) &nbsp;·&nbsp; [**Addons**](#-addons) &nbsp;·&nbsp; [**Guides**](#-guides) &nbsp;·&nbsp; [**Updates**](#-updates)

[![Download the repository](https://img.shields.io/badge/%E2%AC%87%20Download-Repository%20zip-f5c518?style=for-the-badge&labelColor=2a2600)](https://github.com/GoldStart5/Kodi-Game-Launcher/raw/main/zips/repository.kodigamelauncher/repository.kodigamelauncher-1.0.1.zip)

</div>

---

## ✨ Highlights

| | |
|---|---|
| 🎮 **Any game, any store** | Steam, Epic, GOG, emulators and standalone games. A Windows shortcut decides what runs. |
| 🖼️ **Rich library** | Descriptions from IGDB and artwork from SteamGridDB: posters, fanart, logos and more. |
| 🚀 **Launch from Kodi** | Press play and the game starts, with a fullscreen fanart splash while it loads. |
| 🔄 **Automatic updates** | Install the repository once and Kodi keeps every addon up to date. |

## 🧭 How it works

| 1. Organise | 2. Scrape | 3. Play |
|:---:|:---:|:---:|
| Give each game a folder with a `Play.avi` and a `.lnk` shortcut. | The scraper adds each game to your Kodi library with metadata and artwork. | The launcher sees `Play.avi`, shows the splash and starts the shortcut. |

```
Games\
  Hades\
    Play.avi
    Hades.lnk
```

## 📦 Addons

| Addon | What it does |
|---|---|
| **IGDB + SteamGridDB Game Scraper** `metadata.games.igdb` | Fetches game metadata from IGDB and all artwork from SteamGridDB into the Kodi library. |
| **Game Launcher** `service.gamelauncher` | Detects `Play.avi`, shows a fanart splash and launches the game's shortcut. Windows only. |
| **Cinema Themes** `service.cinemathemes` | *Optional.* Plays theme music for your movie, show and game pages through `mpv`. |
| **Theme & Trailer Grabber** `plugin.program.ytgrabber` | *Optional.* Finds and downloads themes and trailers for your library with yt-dlp. |

## 🚀 Install

1. Download the **repository zip** using the button above.
2. In Kodi, open **Add-ons → Install from zip file** and select it.
3. Go to **Install from repository → Kodi Game Launcher Repository** and install the addons you want.
4. Follow the [Installation Guide](Installation-Guide.md) to add your keys and your games.

## 📋 Requirements

- Windows
- Kodi 19 or newer
- A free [Twitch developer app](https://dev.twitch.tv/console) for IGDB metadata
- A free [SteamGridDB API key](https://www.steamgriddb.com/profile/preferences/api) for artwork
- Optional: a separate copy of `mpv.exe` for Cinema Themes

## 📚 Guides

| | |
|---|---|
| 📖 [Installation Guide](Installation-Guide.md) | Full setup, from the repository to your first game. |
| 🛠️ [Troubleshooting](Troubleshooting.md) | What to check when a game won't start or the info is wrong. |
| 📝 [Changelog](CHANGELOG.md) | What changed in each release. |

## 🔔 Updates

Kodi checks the repository about once a day and updates the addons by itself. To check right away, open the repository under **Add-ons → My add-ons** and choose **Check for updates**.

<details>
<summary><b>Need an older version?</b></summary>

<br>

Older versions are kept in the [`zips`](zips) folder, one folder per addon. In Kodi, open an addon's page and choose **Versions** to install an earlier one, or download a zip from the `zips` folder and use **Install from zip file**.

</details>

<details>
<summary><b>Manual install without the repository</b></summary>

<br>

Download the addon zips from the [`zips`](zips) folder and install each one with **Add-ons → Install from zip file**. You will have to update them by hand.

</details>

## 📄 License

Released under the [MIT License](LICENSE).
