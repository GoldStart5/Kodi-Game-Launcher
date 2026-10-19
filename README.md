# Kodi Game Launcher

**Turn Kodi into a console-style frontend for your PC game library.**

![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Kodi](https://img.shields.io/badge/Kodi-17B2E7?style=for-the-badge&logo=kodi&logoColor=white)
![Playnite](https://img.shields.io/badge/Playnite-001F3E?style=for-the-badge)

Kodi Game Launcher is now a **native Kodi addon**. It works together with the Playnite Kodi Exporter to bring your Playnite library into Kodi with metadata and artwork, and it launches games straight from Kodi. No AutoHotkey and no external video player are needed.

## ✨ Features

- 🎮 Kodi game library integration
- 📦 Playnite metadata export (posters, fanart, clear logos)
- 🚀 Launches any Windows shortcut (`.lnk`): Steam, Epic, GOG, emulators, standalone games
- 🖼️ Fullscreen fanart + logo splash while the game loads
- 🎬 Optional custom intro videos (`Play.avi`)
- ⚙️ Settings inside Kodi: trigger name, launch mode, splash on/off, splash timeout

## ⚙️ How It Works

```
Playnite → Playnite Kodi Exporter → Kodi game library
                                          │
                       you select a game in Kodi
                                          │
                            Kodi plays Play.avi
                                          │
              Game Launcher addon (Kodi service) detects it
                                          │
        stops playback → shows fanart splash → launches Game Name.lnk
```

The addon runs as a Kodi service. When the file being played is called `Play.avi` it finds the `.lnk` in the same folder, shows that folder's `fanart` while the game loads, and starts the shortcut. The splash closes when the game (or its launcher) takes the foreground, when the timeout runs out, or when you press Back.

## 🧩 Requirements

| Requirement | Notes |
| --- | --- |
| 🪟 Windows | Uses `os.startfile` to launch shortcuts |
| 📺 Kodi 19 or newer | Addon uses Python 3 |
| 🎯 Playnite | Game library manager |
| 📤 Playnite Kodi Exporter | Exports your library to Kodi format |

## 🚀 Quick Setup

1. Download `service.gamelauncher-<version>.zip` from the [Releases](../../releases) page.
2. In Kodi: **Add-ons → Install from zip file** and pick the zip.
3. Export your Playnite library with Playnite Kodi Exporter.
4. Add a `Play.avi` and a `Game Name.lnk` to every game folder.
5. Import the folder into Kodi (see the [Installation Guide](Installation-Guide.md)).
6. Pick a game in Kodi and play it.

## 📁 Game Folder Layout

```
Game Name
├── Game Name.nfo
├── poster.jpg
├── fanart.jpg        ← shown on the splash
├── clearlogo.png     ← shown on the splash
├── Play.avi          ← the trigger file
└── Game Name.lnk     ← launched by the addon
```

## ⬆️ Upgrading from the AutoHotkey version

1. Close and remove `KodiGameLauncher.ahk` from your Windows Startup folder.
2. Remove the MPV rule for `Play.avi` from `playercorefactory.xml` (or delete the file if you only used it for this project). See the [Installation Guide](Installation-Guide.md#4-keep-playavi-out-of-mpv).
3. Install the addon as above. Your game folders and Kodi library do not change.

## 🎵 Recommended Addon: TV Tunes

Adds theme music to your Kodi library, which works nicely for games: <https://forum.kodi.tv/showthread.php?tid=347428>

## 📚 Documentation

- 📘 [Installation Guide](Installation-Guide.md)
- 🛠️ [Troubleshooting](Troubleshooting.md)

## 📄 License

MIT. See [LICENSE](LICENSE).
