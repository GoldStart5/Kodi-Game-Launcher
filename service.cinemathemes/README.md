# Cinema Themes for Kodi 21 (Windows)

By GoldStart5. Theme music for your video library, played by a portable mpv, with Playnite Sounds style fading.

## Setup

1. Download a Windows build of mpv and unzip it anywhere (a portable folder is fine).
2. In Kodi: Add-ons > Install from zip file > `service.cinemathemes-1.2.4.zip`
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
| Movie list | Root theme of the source folder the focused movie lives in. With no root theme, the focused movie plays its own theme |
| Movie info dialog | The movie's theme, or the root theme if it has none. After closing the dialog the movie's theme keeps playing until you focus another item, then the root theme returns |
| TV show list | Root theme of the TV source folder. With no root theme, the focused show plays its own theme |
| Seasons, episodes, show or episode info | The show's theme, or the root theme if it has none. After leaving seasons or episodes back to the show list, the show's theme keeps playing until you focus another show (closing a show's info dialog goes straight back to the root) |
| Outside the video library (home, settings...) | The global theme if one is set, otherwise the library theme fades out and pauses |
| In the library when no other theme applies | The global theme, if one is set |
| Kodi loses focus / Kodi plays media | Fades out and pauses, then fades in and resumes |

Fades: **Normal fade-in/out** are used when a theme starts from silence, fades out to silence, and for focus, media and library changes. **Switch fade-out/in** (200 to 5000 ms, default 1000) are used when one theme changes to another.

## Library theme toggles (Behaviour tab)

While browsing a list, the first of these that applies plays:

1. **Use the root theme** (on): the theme in the source folder. If it is off or no root theme is found, go to the next.
2. **Global theme replaces the root theme** (on): the global theme takes the root theme's place. Needs the global theme enabled with a folder set.
3. **Hovering plays each movie or show's own theme** (on): used only when 1 and 2 do not cover the lists. Off means nothing plays while hovering, only inside info dialogs, seasons and episodes.

Info dialogs, seasons and episodes always play the item's own theme first. A theme made sticky by an info dialog (movies) or by entering a show keeps playing in the list until you focus another item, whatever these toggles are set to. Then the chain above applies, and if nothing applies the theme fades out to silence.

## Global theme

Turn **Enable global theme** on and set **Global theme folder** (Global theme tab) to a folder of audio files, for example `theme 1.mp3`, `theme 2.mp3`, `theme 3.mp3`. Every audio file in it is used. It plays outside the video library, and inside it when no other theme applies. It has its own order (random or in order), loop (on by default), random start position, and a choice of what happens when you return to it: **resume where it left off** or **start a new track**. Fades: going from a library theme to the global theme uses the normal fades, going from the global theme to a library theme uses the switch fades, and fading it out to silence (focus loss, media playing) uses the normal fade-out. With the switch off, or no global folder set, nothing plays outside the library.

Several themes in one folder are queued: random shuffles them, in order plays them by file name.

## Notes

- Focus detection uses the Windows foreground window, so no AutoHotkey is needed.
- mpv runs without its config file (`--no-config`). To choose an audio device, use **Extra mpv arguments**,
  for example `--audio-device=wasapi/{device-id}` (list devices with `mpv --audio-device=help`).
- mpv is tied to Kodi with a Windows job object, so it closes with Kodi even if Kodi crashes.
- Turn on **Enable debug logging** (Advanced) and check `kodi.log` for lines starting with `[service.cinemathemes]`.

## Root themes and settings help

Root themes (the theme file in your movie or show source folder) have their own **order**, **loop** and **random start** settings under *Player and fades > Root themes*. They are independent from the settings for movie and show themes.

Every setting has a short description that Kodi shows at the bottom of the settings window when the setting is highlighted.
