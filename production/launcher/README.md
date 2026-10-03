# Tester launcher

`Play-StarWarsTest.cmd` starts Battle for Wesnoth 1.19 (Windows) with the
latest **published** add-on (`origin/main`), for playtesting:

- It exports the add-on read-only with `git archive`, so it works while
  development has uncommitted work and never shows unreviewed content.
- It mirrors the add-on into isolated test userdata at
  `%LOCALAPPDATA%\WesnothStarWarsTest\userdata`, where saves and preferences
  persist between test sessions.
- It opens the title screen; choose **Campaigns**, then any of the three
  Thrawn Trilogy campaigns and a difficulty.

Install, or update after the launcher changes, from Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File \\wsl.localhost\Ubuntu-24.04\home\willj\projects\wesnoth-starwars\production\launcher\Install-StarWarsTestShortcut.ps1
```

This puts **Star Wars - Thrawn Trilogy (Test)** on the desktop. Set
`WESNOTH_PLAY_VALIDATE_ONLY=1` to refresh the add-on without starting the game.

## Private audio overlay

The project's private sound set lives only in the private
`weberwe3/wesnoth-starwars-private-audio` repository. It is never committed
here or packaged with the add-on. On a machine that has that repository
cloned next to this one (`/home/willj/projects/wesnoth-starwars-private-audio`
in WSL, or set `WESNOTH_PRIVATE_AUDIO_LINUX`), the launcher pulls it and runs
its `apply_private_audio.py` on the freshly installed test copy every time,
so the sounds survive the add-on refresh. Without the clone, or without
access to it, the launcher continues with the standard sounds. The result is
recorded as `private_audio=` in `wesnoth-starwars-launch.txt` in the test
userdata.

To set up a machine:

```bash
git clone https://github.com/weberwe3/wesnoth-starwars-private-audio ~/projects/wesnoth-starwars-private-audio
```

`agent/runtime/Play-WesnothStarWars.cmd` is the coordinator's governed launcher;
it refuses to start while the development checkout has uncommitted changes.
