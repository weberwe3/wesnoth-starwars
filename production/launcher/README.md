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

`agent/runtime/Play-WesnothStarWars.cmd` is the coordinator's governed launcher;
it refuses to start while the development checkout has uncommitted changes.
