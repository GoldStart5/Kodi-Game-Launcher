# Kodi Game Launcher + KodiGameMediaExporter

## Installation Guide

Kodi Game Launcher turns Kodi into a complete PC gaming frontend.

It combines:

- Playnite for managing games and metadata.
- KodiGameMediaExporter for creating a Kodi-compatible local game library.
- Kodi Game Launcher for launching Windows games from Kodi.

The result is a console-style gaming experience inside Kodi with:

- Game metadata
- Artwork
- Clear logos
- Custom intro videos
- Game launcher

---

# Overview

The system works by connecting Kodi's media library with Windows game shortcuts.

Each game folder contains a `Play.avi` trigger file and a Windows shortcut (`.lnk`).

When a game is selected in Kodi:

1. Kodi opens `Play.avi`.
2. Kodi sends the file to MPV.
3. Kodi Game Launcher detects the MPV playback.
4. The launcher identifies the game folder.
5. The launcher finds the matching shortcut.
6. Windows launches the game.

---

# Complete Workflow

```text
Playnite
   |
   v
Manage games and metadata
   |
   v
KodiGameMediaExporter
   |
   v
Kodi Local Game Library
   |
   v
Add game shortcuts manually
   |
   v
Kodi displays games
   |
   v
User selects game
   |
   v
Kodi opens Play.avi
   |
   v
MPV plays Play.avi
   |
   v
Kodi Game Launcher detects playback
   |
   v
Launcher starts Game Name.lnk
   |
   v
Game launches
When a game is selected in Kodi:

1. Kodi opens `Play.avi`.
2. Kodi sends the file to MPV.
3. Kodi Game Launcher detects the MPV playback.
4. The launcher identifies the game folder.
5. The launcher finds the matching shortcut.
6. Windows launches the game.

---

# Complete Workflow

```text
Playnite
   |
   v
Manage games and metadata
   |
   v
KodiGameMediaExporter
   |
   v
Kodi Local Game Library
   |
   v
Add game shortcuts manually
   |
   v
Kodi displays games
   |
   v
User selects game
   |
   v
Kodi opens Play.avi
   |
   v
MPV plays Play.avi
   |
   v
Kodi Game Launcher detects playback
   |
   v
Launcher starts Game Name.lnk
   |
   v
Game launches

---

# Add Game Shortcuts Manually

## Important

Before using Kodi to launch games, you must manually add a game shortcut inside each exported game folder.

For every exported game folder, create a Windows shortcut (`.lnk`) pointing to:

- The game's executable
- Steam launcher
- Epic Games launcher
- GOG launcher
- Emulator
- Custom launcher

Example:

```text
KodiGameMedia
|
+-- Game Name
    |
    +-- Game Name.nfo
    +-- poster.jpg/png
    +-- fanart.jpg/png
    +-- clearlogo.png
    +-- Play.avi
    +-- Game Name.lnk

---

# KodiGameMediaExporter Features

- Exports Playnite games to Kodi local format
- Creates Kodi ".nfo" files
- Exports cover artwork
- Exports background artwork
- Supports Extra Metadata Loader logos
- Converts "Logo.png" into Kodi "clearlogo.png"
- Keeps existing Kodi files safe
- Adds missing artwork during updates

---

# Extra Metadata Loader ClearLogo Support

KodiGameMediaExporter reads logos from:

```text
%AppData%\Playnite\ExtraMetadata\games\<GameID>\Logo.png
