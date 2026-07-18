# Kodi Game Launcher + KodiGameMediaExporter  
## Complete Installation Guide

Kodi Game Launcher turns Kodi into a complete PC gaming frontend.

It combines:

- **Playnite** for managing games and metadata.
- **KodiGameMediaExporter** for creating a Kodi-compatible local game library.
- **Kodi Game Launcher** for launching Windows games directly from Kodi.

The result is a console-style gaming experience inside Kodi with:

- Game metadata
- Artwork
- Clear logos
- Custom intro videos
- Game launcher integration


---

# Overview

The system works by connecting Kodi's media library with Windows game shortcuts.

Each game folder contains:

- A `Play.avi` trigger file.
- A Windows shortcut (`.lnk`) used to launch the game.

When a game is selected in Kodi:

1. Kodi opens `Play.avi`.
2. Kodi sends the file to MPV.
3. Kodi Game Launcher detects the MPV playback event.
4. The launcher identifies the game folder.
5. The launcher finds the matching shortcut.
6. Windows launches the game.


---

# Complete Workflow

```
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
```


---

# Requirements

## Hardware / Software

Required:

- Windows PC
- Kodi installed
- Playnite installed
- AutoHotkey v2
- KodiGameMediaExporter installed
- Kodi Game Launcher installed
- Portable MPV included with launcher


---

# Installation

## Before Installation

Before installing Kodi Game Launcher:

1. Install Kodi.
2. Close Kodi.
3. Make sure AutoHotkey v2 is installed or available.


---

## Kodi Game Launcher Installer

The Kodi Game Launcher installer will:

- Install Kodi Game Launcher.
- Install portable MPV.
- Configure MPV.
- Install AutoHotkey v2 if required.
- Add Kodi `playercorefactory.xml` integration.
- Add `KodiGameLauncher.ahk` to Windows Startup.
- Configure required paths.


---

# KodiGameMediaExporter

## What Is KodiGameMediaExporter?

KodiGameMediaExporter is a Playnite extension designed for users who want Kodi to act as their gaming frontend.

It exports your Playnite game library into a Kodi-compatible local media structure using:

- Playnite game metadata
- Cover artwork
- Background artwork
- Extra Metadata Loader logos


The exported library can then be imported into Kodi as a local media collection.


---

# Installing KodiGameMediaExporter

Copy the:

```
KodiGameMediaExporter
```

folder into your Playnite extensions directory:

```
%AppData%\Playnite\Extensions\
```

The final location should be:

```
%AppData%\Playnite\Extensions\KodiGameMediaExporter\
```

The folder should contain:

```
KodiGameMediaExporter
|
└── KodiGameMediaExporter.psm1
```


Restart Playnite after installation.


---

# Using KodiGameMediaExporter

Open Playnite:

```
Playnite Logo
      ↓
Kodi
      ↓
Export Kodi Local Metadata
```

Select the folder where you want your Kodi game media exported.

The exporter will create your Kodi game library structure.


---

# Export Structure

The exporter creates:

```
KodiGameMedia
|
+-- Game Name
    |
    +-- Game Name.nfo
    +-- poster.jpg/png
    +-- fanart.jpg/png
    +-- clearlogo.png
```


---

# Add Game Shortcuts Manually

## Important

Before using Kodi to launch games, you must manually add a Windows shortcut inside every exported game folder.

For every exported game folder, create a shortcut:

```
Game Name.lnk
```

The shortcut can point to:

- Game executable
- Steam launcher
- Epic Games launcher
- GOG launcher
- Emulator
- Custom launcher


Example:

```
KodiGameMedia
|
+-- Game Name
    |
    +-- Game Name.nfo
    +-- poster.jpg
    +-- fanart.jpg
    +-- clearlogo.png
    +-- Play.avi
    +-- Game Name.lnk
```


## Shortcut Naming Rule

The shortcut name must match the game folder name.

Example:

Folder:

```
Cyberpunk 2077
```

Shortcut:

```
Cyberpunk 2077.lnk
```

Kodi Game Launcher uses this shortcut when launching the game.


---

# Kodi Game Launcher

## How It Works

Kodi Game Launcher monitors MPV playback.

When Kodi opens:

```
Play.avi
```

the launcher:

1. Finds the folder containing `Play.avi`.
2. Searches that folder for a `.lnk` shortcut.
3. Launches the shortcut.


Kodi Game Launcher does not need to know which platform the game uses.

It only launches the shortcut.


---

# The Importance of Play.avi

`Play.avi` is the connection between Kodi and Kodi Game Launcher.

It is not only an intro video.

It acts as the trigger file that allows Kodi Game Launcher to detect the selected game.

Kodi uses:

```
Play.avi
```

as the playable media item.

The launcher uses the MPV playback event to:

- Detect the selected game.
- Locate the correct folder.
- Find the shortcut.
- Launch the game.


Without `Play.avi`:

- Kodi may not create a playable game entry.
- Kodi Game Launcher receives no playback event.
- Game launching will not work.


---

# Complete Game Folder Structure

A finished game folder should contain:

```
KodiGameMedia
|
+-- Game Name
    |
    +-- Game Name.nfo
    +-- poster.jpg
    +-- fanart.jpg
    +-- clearlogo.png
    +-- Play.avi
    +-- Game Name.lnk
```


---

# File Information

## Game Name.nfo

Kodi metadata file created by KodiGameMediaExporter.

Contains:

- Game title
- Description
- Metadata information


---

## poster.jpg / poster.png

Game cover artwork.


---

## fanart.jpg / fanart.png

Background artwork displayed by Kodi skins.


---

## clearlogo.png

Kodi clear logo artwork.

Created from Playnite Extra Metadata Loader logos.


---

## Play.avi

Required Kodi Game Launcher trigger file.

Can contain:

- Game intro animation
- Retro gaming intro
- Any video you want


Filename must always be:

```
Play.avi
```


---

## Game Name.lnk

Windows shortcut used to launch the game.

Example:

```
Game Name.lnk
```

The shortcut can point to:

- Steam games
- Epic Games games
- GOG games
- Emulators
- Standalone games
- Custom launchers


---

# KodiGameMediaExporter Features

Features:

- Exports Playnite games to Kodi local format
- Creates Kodi `.nfo` files
- Exports cover artwork
- Exports background artwork
- Supports Extra Metadata Loader logos
- Converts `Logo.png` into Kodi `clearlogo.png`
- Keeps existing Kodi files safe
- Adds missing artwork during updates


---

# Extra Metadata Loader ClearLogo Support

KodiGameMediaExporter reads logos from:

```
%AppData%\Playnite\ExtraMetadata\games\<GameID>\Logo.png
```

and exports them as:

```
clearlogo.png
```

for Kodi.


---

# Updating Existing Libraries

Running the exporter again will:

- Add new games.
- Add missing artwork.
- Keep existing `.nfo` files.
- Keep existing artwork.
- Avoid replacing Kodi customizations.


---

# Kodi Setup

After your game folders contain:

```
Game Name
|
+-- Game Name.nfo
+-- poster.jpg
+-- fanart.jpg
+-- clearlogo.png
+-- Play.avi
+-- Game Name.lnk
```

configure Kodi.


---

# Set Kodi To Use Local Information Only

1. Open:

```
Settings → Media → Library → Videos
```

2. Locate your exported games folder.

3. Open the context menu.

4. Select:

```
Set content
```

5. Configure:

```
This directory contains:
Movies

Information provider:
Local information only
```

6. Enable:

```
✓ Movies are in separate folders that match the movie title
```

7. Press:

```
OK
```

Kodi will now use the local metadata stored inside your exported game folders.


---

# Create A Smart Playlist

Create a Kodi Smart Playlist pointing to your game folder.

Recommended rule:

```
Path → contains → your games folder path
```

Example:

```
D:\Games\
```

This automatically includes your exported games.


---

# Add Games To Kodi Home Screen

For the best experience:

1. Create your Smart Playlist.
2. Add the playlist to the Kodi home screen.
3. Use a custom Kodi skin.


The default Kodi skin has limited customization options.


---

# Recommended Kodi Skin

## Arctic Fuse 3

Recommended for Kodi Game Launcher.

Features:

- Modern interface
- Console-style browsing
- Custom home menus
- Playlist support
- Large library support


Other Jurialmunkey skins may also work depending on your setup.


---

# Custom Intro Videos

Every game can have its own custom:

```
Play.avi
```

Example:

```
Games
|
+-- Game 1
|   |
|   +-- Play.avi
|
+-- Game 2
    |
    +-- Play.avi
```

The launcher automatically detects the correct game folder.

This allows every game to have a unique intro animation.


---

# Troubleshooting

See:

```
troubleshooting.txt
```


---

# Enjoy Kodi Game Launcher

Use Kodi as your complete gaming frontend with:

- Playnite-powered metadata
- Kodi local library support
- Artwork
- Clear logos
- Custom intro videos
- Windows game launching


```
