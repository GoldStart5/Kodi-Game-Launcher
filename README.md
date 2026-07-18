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
- Launch games from Kodi
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

## Quick Setup

1. Export your Playnite library using KodiGameMediaExporter.
2. Add a `.lnk` shortcut to each game folder.
3. Add `Play.avi` to each game folder.
4. Import the library into Kodi.
5. Launch games from Kodi.

## Documentation

See:

- `README.txt` - Full installation and configuration guide
- `troubleshooting.txt` - Troubleshooting information
