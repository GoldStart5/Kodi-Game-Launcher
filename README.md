# Kodi Game Launcher

A complete PC gaming frontend solution for Kodi.

Kodi Game Launcher connects Kodi with Windows game launching by using
`Play.avi` as the trigger file. Combined with KodiGameMediaExporter,
it allows Playnite game libraries to be exported into Kodi with metadata,
artwork.

## Features

- Kodi game library integration
- Playnite metadata export
- Local Kodi media support
- Game Launcher
- Custom intro videos
- Steam, Epic, GOG, emulator, and standalone game support

## How It Works

Playnite  
↓  
KodiGameMediaExporter  
↓  
Kodi Game Library  
↓  
Play.avi detected  
↓  
Kodi Game Launcher  
↓  
Game shortcut launched

## Requirements

- Windows
- Kodi
- Playnite
- AutoHotkey v2

## Recommended Addons

### TV Tunes

Recommended for adding custom theme music and intro sounds to Kodi libraries.

Features:

- TV show theme music
- Background audio
- Custom library atmosphere
- Works well with custom Kodi skins

TV Tunes repository:

https://github.com/tvaddonsco/script.tvtunes

## Quick Setup

1. Install Kodi Game Launcher
2. Export your Playnite library using KodiGameMediaExporter.
3. Add a `.lnk` shortcut to each game folder.
4. Add `Play.avi` to each game folder.
5. Import the library into Kodi.
6. Launch games from Kodi.

## Documentation

Complete installation instructions and troubleshooting are included with the download.

- 📘 [Full Installation Guide](Installation-Guide.md)
- 🛠️ [Troubleshooting](troubleshooting.md)
