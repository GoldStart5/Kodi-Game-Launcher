# Installation Guide

Playnite is not needed. You need Kodi (19 or newer) on Windows, the two addons from this repository, and a folder for each game.

## 1. Install the repository

1. Download [repository.kodigamelauncher-1.0.1.zip](https://github.com/GoldStart5/Kodi-Game-Launcher/raw/main/zips/repository.kodigamelauncher/repository.kodigamelauncher-1.0.1.zip).
2. In Kodi, go to **Settings → Add-ons → Install from zip file** and pick it. If Kodi asks, allow installs from unknown sources.

## 2. Install the addons

Go to **Add-ons → Install from repository → Kodi Game Launcher Repository** and install:

- **Game Launcher** (under Services)
- **IGDB + SteamGridDB Game Scraper** (under Information providers → Movie information providers)
- **Cinema Themes** (optional, under Services): plays a `theme` music file from each movie or show folder while you browse. It needs a separate copy of `mpv.exe`.

## 3. Get your free keys

- **IGDB:** create an app at [dev.twitch.tv/console](https://dev.twitch.tv/console) to get a Client ID and Client Secret.
- **SteamGridDB:** create an API key at [steamgriddb.com/profile/preferences/api](https://www.steamgriddb.com/profile/preferences/api).

## 4. Enter your keys in the scraper

> **Important:** enter the keys in the scraper's own Configure page, **not** in the settings that appear while you set the content of a media source. Keys entered in the Set content dialog are not saved, and the scraper will find no metadata or artwork.

1. Go to **Add-ons → My add-ons → Information providers → Movie information providers**.
2. Open **IGDB + SteamGridDB Game Scraper** and choose **Configure**.
3. Enter your Twitch Client ID, Twitch Client Secret and SteamGridDB API key, then press OK.

Do this before you add your games in step 6.

## 5. Create a folder for each game

Put every game in its own folder, named after the game:

```
Games\
  Hades\
    Play.avi
    Hades.lnk
  Celeste\
    Play.avi
    Celeste.lnk
```

- `Play.avi` is a short video that Kodi plays to start the launch. It must be a valid video file.
- The `.lnk` shortcut starts the game. Name it after the folder. If a folder has several shortcuts, the one matching the folder name is used.

## 6. Add the games to Kodi

1. Go to **Videos → Files → Add videos**, browse to your `Games` folder and add it.
2. Set the content to **Movies** and choose **IGDB + SteamGridDB Game Scraper** as the information provider.
3. Turn on the folder option (each movie is in its own folder), then confirm and let Kodi scan.

Don't enter your keys here. If you skipped step 4, cancel, do it first, then come back.

Your games now show up with descriptions and artwork, but they are stored as movies, so they will also appear in your normal Movies list. The next step keeps them apart.

## 7. Separate games from movies with smart playlists

Create two smart playlists, so games and movies each get their own list.

**Games playlist**
1. Go to **Videos → Playlists** and choose **New smart playlist**.
2. Set the type to **Movies**.
3. Add a rule: **Path** → **contains** → the name of your games folder (for example `Games`).
4. Give it a name such as `Games`, then save it.

**Movies playlist**
1. Create another smart playlist of type **Movies**.
2. Add a rule: **Path** → **does not contain** → the same games folder name.
3. Give it a name such as `Movies`, then save it.

Use text that appears only in your games path. For example, if your games are in `D:\Games` and your movies in `D:\Movies`, the word `Games` is enough. If your movie path also contains that word, use more of the games path, such as `D:\Games`.

Add the playlists to your home screen as menu items or widgets. How you do that depends on your skin, and most skins let you pick a playlist when you customise a menu item or widget. A custom skin helps here.

## 8. Launcher settings

Open **Add-ons → My add-ons → Services → Game Launcher → Configure**.

- **Trigger file name:** the file that starts a launch (default `Play.avi`).
- **Launch the game:** immediately, or after the intro video finishes.
- **Fanart splash:** shown while the game loads, with optional animation.
- **Show splash before launching the game (seconds):** how long the splash shows before the game starts (1 to 7 seconds).
- **Longest wait for the game to open (seconds):** the splash closes after this time at the latest.
- **Update Last played:** records the launch in Kodi's "Last played" while keeping the game unwatched.
- **Splash zoom style:** zoom in then out, zoom out then in, or random.
- **Artwork source:** Kodi library first, local files first, or local files only.

If games open behind Kodi, set Kodi's display mode to **Fullscreen Window** in the display settings.

## Optional: sharper artwork

In the scraper's Configure page (see step 4), turn on **Full-resolution art** and restart Kodi. This edits `advancedsettings.xml` to stop Kodi downscaling images.

The same page lets you choose the **SteamGridDB fanart size** (3840x1240, 1920x620 or both) and optionally add IGDB artworks and screenshots to the fanart list.

## Updates

Kodi checks the repository by itself and updates both addons. You don't need to download anything again.
