# Kodi Game Launcher: Troubleshooting

## First, check the log

The addon writes to Kodi's log with the prefix `[service.gamelauncher]`. The log is at `%APPDATA%\Kodi\kodi.log`. You should see lines such as:

```
[service.gamelauncher] Service started
[service.gamelauncher] Trigger file playing: D:\Games\Game Name\Play.avi
[service.gamelauncher] Launching D:\Games\Game Name\Game Name.lnk
```

Where the sequence stops tells you which step failed.

## Nothing happens when I play a game

- **No "Service started" line:** the addon isn't installed or isn't enabled. Go to **Add-ons → My add-ons → Services** and check that Game Launcher is listed and enabled, then restart Kodi.
- **"Service started" but no "Trigger file playing" line:** Kodi isn't playing `Play.avi` with its own player. See the next section.
- **"Trigger file playing" but no "Launching" line:** the folder has no `.lnk` (a "No .lnk shortcut found" notification will appear), or you are using *After the intro video finishes* mode and the video was stopped before it ended.

## Play.avi opens in MPV (or another external player)

Your `playercorefactory.xml` still sends `.avi` files to an external player.

1. Open `%APPDATA%\Kodi\userdata\playercorefactory.xml`.
2. Put `<rule filetypes="avi" player="default"/>` as the first rule inside `<rules action="prepend">`.
3. Remove `avi` from any `filetypes` list that points to an external player.
4. Restart Kodi.

If you only used the file for this project, delete it instead.

## Play.avi is not detected

- The file name must be `Play.avi` (or match the **Trigger file name** setting).
- `Play.avi` and the `.lnk` must be in the **same folder**. A subfolder won't work.
- Kodi must play the real file. Check that the library item points to the game folder and not to a different file.

## "No .lnk shortcut found"

Add a Windows shortcut to the game folder. It should be named after the folder (`Game Name.lnk`). If no name matches, the first `.lnk` in the folder is used.

## The shortcut launches the wrong game, or does nothing

The addon only starts the shortcut, so test it first: double-click the `.lnk` in Windows. Check its target, "Start in" folder, and arguments.

## The game opens but is behind Kodi

Enable **Settings → System → Display → Fullscreen Window**. If Windows still keeps Kodi in front, make sure the game or launcher is not set to start minimized.

## The splash closes too early

The splash closes when another app takes the foreground. Some launchers show a small window first, which counts. Turn the splash off in the addon settings if that is distracting, or leave it and accept the early close.

## The splash stays too long

It stays until another app gets the foreground, the timeout runs out, or you press Back. Lower **Splash timeout** in the addon settings.

## The video flashes before the game starts

Use **Immediately** mode with a very short, black `Play.avi`, or switch to **After the intro video finishes** if you want the video to play.

## Games don't appear in Kodi

- Check that the folder was scanned and its content type is set to **Movies** with **Local information only**.
- Confirm the smart playlist path points to your games folder.
- Make sure each game folder has a valid `.nfo` from the exporter.

## Still stuck

Run through the chain and find the step that fails: Kodi plays `Play.avi` → addon logs "Trigger file playing" → `.lnk` found → "Launching" → game starts. Include the `[service.gamelauncher]` lines from `kodi.log` when you open an issue.
