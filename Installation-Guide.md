# Kodi Game Launcher: Installation Guide

Kodi Game Launcher is a Kodi service addon that launches Windows games from Kodi. It combines:

- **Playnite** to manage games and metadata
- **Playnite Kodi Exporter** to create a Kodi-compatible local game library
- **Game Launcher addon** (`service.gamelauncher`) to start games from Kodi

No AutoHotkey and no external player are required.

## How it works

Each game folder contains a `Play.avi` trigger file and a Windows shortcut (`.lnk`).

1. You select a game in Kodi and Kodi plays `Play.avi` with its own player.
2. The addon sees that `Play.avi` is playing.
3. It stops the video (or waits for the intro to finish, depending on your setting).
4. It shows the game's fanart and logo full screen.
5. It launches the `.lnk` found in the same folder.
6. The splash closes once the game or its launcher comes to the foreground.

## Requirements

- Windows PC
- Kodi 19 or newer
- Playnite
- Playnite Kodi Exporter

## 1. Install the addon

1. Download `service.gamelauncher-<version>.zip` from the Releases page. Do not unzip it.
2. In Kodi go to **Settings → Add-ons → Install from zip file**. If asked, allow installs from unknown sources.
3. Select the zip. Kodi shows a notification when the addon is installed.

The addon starts automatically with Kodi. Restart Kodi once after installing.

## 2. Export your library from Playnite

1. In Playnite, drag the Playnite Kodi Exporter `.pext` file into the window, confirm, and restart Playnite.
2. Open the Playnite menu → **Kodi → Export Kodi Local Metadata**.
3. Choose the folder for your Kodi game media.

The exporter creates:

```
KodiGameMedia
└── Game Name
    ├── Game Name.nfo
    ├── poster.jpg/png
    ├── fanart.jpg/png
    └── clearlogo.png
```

Running the exporter again adds new games and missing artwork without replacing existing files.

## 3. Add Play.avi and the shortcut to every game folder

```
KodiGameMedia
└── Game Name
    ├── Game Name.nfo
    ├── poster.jpg
    ├── fanart.jpg
    ├── clearlogo.png
    ├── Play.avi
    └── Game Name.lnk
```

- **`Play.avi`**: the trigger. The file name must be `Play.avi` (not case sensitive) unless you change it in the addon settings. It can be any video: a short intro, or a 1-second black clip if you want no intro.
- **`Game Name.lnk`**: a Windows shortcut to the game, Steam, Epic, GOG, an emulator, or any launcher. Name it after the folder. If the folder has no matching name, the first `.lnk` found is used.

Each game can have its own `Play.avi`.

## 4. Keep Play.avi out of MPV

Older versions of this project sent video to MPV through `playercorefactory.xml`. The addon needs Kodi's own player to play `Play.avi`, so make sure no rule sends `.avi` files to an external player.

- **You only had this file for Kodi Game Launcher:** delete `%APPDATA%\Kodi\userdata\playercorefactory.xml` and restart Kodi.
- **You use it for other things (for example MPV for all other video):** add this rule as the **first** rule inside `<rules action="prepend">`, because the first match wins:

```xml
<rule filetypes="avi" player="default"/>
```

and remove `avi` from any `filetypes` list that targets your external player. To limit the exception to the trigger file only, use:

```xml
<rule filename=".*[\\/]play\.avi" player="default"/>
```

Restart Kodi after changing the file.

## 5. Set up the Kodi library

1. Open **Settings → Media → Library → Videos**, then add your exported games folder as a source.
2. Open the context menu on it and choose **Set content**:
   - This directory contains: **Movies**
   - Information provider: **Local information only**
   - Enable **Movies are in separate folders that match the movie title**
3. Press **OK** and let Kodi scan.

### Smart playlist and home screen

1. Create a Smart Playlist with the rule **Path → contains → your games folder** (for example `D:\Games\`).
2. Add the playlist to the Kodi home screen. Use a skin that supports custom home menu items, as the default skin has limited customization.

### Display setting

Go to **Settings → System → Display** and enable **Fullscreen Window** so games open on top of Kodi.

## 6. Addon settings

Open **Add-ons → My add-ons → Services → Game Launcher → Configure**.

| Setting | What it does |
| --- | --- |
| Trigger file name | The file that starts a launch. Default `play.avi`. |
| Launch the game | **Immediately** stops the video and launches. **After the intro video finishes** lets `Play.avi` play to the end first. Stopping the video yourself cancels the launch. |
| Show fanart splash | Shows `fanart` and `clearlogo` full screen while the game loads. |
| Splash timeout | Longest time the splash stays up (default 30 seconds). |

The splash closes earlier if another application takes the foreground, or if you press Back.

## Custom intro videos

Put a different `Play.avi` in each game folder for a unique intro per game. Use **After the intro video finishes** in the settings to play intros in full before the game starts.

## Notes and limits

- Works with local drives and Windows network (UNC) paths. Kodi-only sources such as `smb://` can't be launched, because Windows needs a real path.
- In **Immediately** mode the video may flash for a moment before it is stopped. A very short black `Play.avi` hides this.
- The addon detects the game by watching which window is in front. It can't see inside the game itself.

Problems? See [Troubleshooting](Troubleshooting.md).
