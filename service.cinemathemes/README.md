# Cinema Themes for Kodi 21 (Windows)

By GoldStart5. Theme music for your video library, played by a portable mpv, with Playnite Sounds style fading.

## Setup

1. Download a Windows build of mpv and unzip it anywhere (a portable folder is fine).
2. In Kodi: Add-ons > Install from zip file > `service.cinemathemes-1.0.4.zip`
   (allow "Unknown sources" if Kodi asks).
3. Add-on settings: set **Location of mpv.exe**.
4. Put theme files in your folders:
   - `D:\Movies\theme.mp3` is the root theme, played while you browse the movie list
   - `D:\Movies\Alien (1979)\theme.mp3` plays in that movie's info dialog
   - `D:\TV Shows\theme.mp3` is the root theme for the TV show list
   - `D:\TV Shows\Some Show\theme.mp3` plays inside that show (seasons, episodes, info)

Any audio file whose name contains the word `theme` counts (`theme.mp3`, `Main Theme.flac`, ...).

## Behaviour

| Where you are | What plays |
| --- | --- |
| Movie list | Root theme of the source folder the focused movie lives in |
| Movie info dialog | The movie's theme, or the root theme if it has none |
| TV show list | Root theme of the TV source folder |
| Seasons, episodes, show or episode info | The show's theme, or the root theme if it has none |
| Kodi loses focus / Kodi plays media / outside the library | Fades out and pauses, then fades in and resumes |

Several themes in one folder are queued: random shuffles them, in order plays them by file name.

## Notes

- Focus detection uses the Windows foreground window, so no AutoHotkey is needed.
- mpv runs without its config file (`--no-config`). To choose an audio device, use **Extra mpv arguments**,
  for example `--audio-device=wasapi/{device-id}` (list devices with `mpv --audio-device=help`).
- mpv is tied to Kodi with a Windows job object, so it closes with Kodi even if Kodi crashes.
- Turn on **Enable debug logging** (Advanced) and check `kodi.log` for lines starting with `[service.cinemathemes]`.
