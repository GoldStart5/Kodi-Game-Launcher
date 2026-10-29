# Troubleshooting

When a game doesn't start, follow the chain and find the step that fails:

Kodi plays `Play.avi` → Game Launcher detects it → playback stops → the `.lnk` is found → the shortcut starts.

Kodi's log (`%APPDATA%\Kodi\kodi.log`) shows each step. Search for `service.gamelauncher`.

## Nothing happens when I press play

- Check that the Game Launcher service is installed and enabled.
- Check that the folder contains a file named exactly like the trigger name (default `Play.avi`) and that it is a valid video.
- In the log, look for `Trigger file playing`. If it's missing, the filename or the trigger setting doesn't match.

## "No .lnk shortcut found"

The game folder needs a shortcut next to `Play.avi`. Make sure it ends in `.lnk` and sits in the same folder.

## The wrong game starts

The launcher only runs the shortcut. Check the shortcut's target path, start-in folder and arguments. If the folder has several shortcuts, the one named after the folder is used.

## The game opens behind Kodi

Set Kodi's display mode to **Fullscreen Window**.

## The splash stays on screen

It closes when the game takes focus, when the timeout runs out, or when you press Back. If your game is slow to start, raise the splash timeout in the Game Launcher settings.

## No splash artwork

The splash uses the game's fanart from the Kodi library or the game folder. Change the **Artwork source** setting, or rescan the game so the scraper fetches artwork.

## A game is missing, or has the wrong info

- Make sure the folder is inside a source set to **Movies** with the IGDB + SteamGridDB scraper.
- Name the folder after the game as it appears on IGDB. Remove extra text like version numbers.
- Check that your Twitch and SteamGridDB keys are saved. Enter them in **Add-ons → My add-ons → Information providers → Movie information providers → IGDB + SteamGridDB Game Scraper → Configure**. Keys typed into the Set content dialog are not saved. Without IGDB keys, only artwork is found.
- To retry a game, remove it from the library and scan again.

## Artwork looks blurry

Turn on **Full-resolution art** in the scraper's Configure page and restart Kodi.

## An update isn't showing

Kodi checks about once a day. To check now, go to **Add-ons → My add-ons**, open the repository and choose **Check for updates**.
