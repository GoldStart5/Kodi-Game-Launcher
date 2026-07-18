Kodi Game Launcher
Troubleshooting
================


Game Does Not Launch
--------------------

Check the following:

1. The game folder contains:

   Play.avi

2. The game folder contains a shortcut:

   Game Name.lnk

3. The shortcut works correctly when opened manually in Windows.

4. Kodi Game Launcher is running.


MPV Plays The Video But Nothing Happens
---------------------------------------

Possible causes:

- Kodi Game Launcher is not running.
- AutoHotkey v2 is missing.
- The shortcut file is missing.
- The shortcut is not inside the same folder as Play.avi.

The launcher requires:

Game Folder
|
+-- Play.avi
+-- Game Name.lnk


Kodi Does Not Play Play.avi
---------------------------

Check:

- playercorefactory.xml is installed correctly.
- Kodi is using MPV for AVI files.
- MPV installation folder has not been moved.
- Play.avi is a valid playable video file.


Game Does Not Appear In Kodi
----------------------------

Check:

- The game folder contains Play.avi.
- Kodi has scanned the correct library folder.
- Your Kodi playlist points to the correct location.
- The game folder contains valid metadata.


Shortcut Launches The Wrong Game
--------------------------------

Open the shortcut properties.

Verify:

- Target path.
- Working directory.
- Launcher arguments.

Kodi Game Launcher only starts the shortcut.
The shortcut controls what application is launched.


Moved Installation Folder
-------------------------

Do not move the Kodi Game Launcher folder after installation.

Moving the folder can break:

- MPV path configuration.
- Kodi playercorefactory.xml settings.
- Startup launcher path.


Custom playercorefactory.xml Problems
-------------------------------------

If you already had a custom playercorefactory.xml:

1. Restore your backup.
2. Add the Kodi Game Launcher MPV rules manually if required.

Do not overwrite custom Kodi player settings without a backup.


Play.avi Is Not Detected
------------------------

Make sure:

- The filename is exactly:

  Play.avi

- The file is inside the same folder as the game shortcut.
- MPV is playing that exact file.

Example:

Correct:

Games
|
+-- Example Game
    |
    +-- Play.avi
    +-- Example Game.lnk


Incorrect:

Games
|
+-- Example Game
    |
    +-- Videos
        |
        +-- Play.avi


AutoHotkey Problems
-------------------

Verify:

- AutoHotkey v2 is installed.
- KodiGameLauncher.ahk exists.
- The script exists in:

%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup


Multiple AutoHotkey Scripts
---------------------------

Do not delete all AutoHotkey scripts.

Only remove:

KodiGameLauncher.ahk

Other scripts may belong to different programs.


Still Not Working
-----------------

Check the complete chain:

Kodi
 |
 v
Play.avi opens
 |
 v
MPV starts playback
 |
 v
KodiGameLauncher detects MPV
 |
 v
Game folder detected
 |
 v
.lnk shortcut found
 |
 v
Game launches


If one step fails, that identifies where the problem is located.
