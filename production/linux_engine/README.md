# Linux Wesnoth GUI harness

Automated GUI checks run on a Linux build of the **same engine version** as
the player's Windows install (Battle for Wesnoth 1.19.27), using SDL3's
`offscreen` video driver and `dummy` audio. No desktop session, display server,
or login is required, so unattended and disconnected-desktop runs work.

## Why

The Windows GUI probe could never reach a playable `Game` context. The root
cause is in the engine, not the desktop: `src/game_launcher.cpp` sets
`jump_to_campaign_.jump = false` whenever `--plugin` is given, so `--campaign`
is silently ignored and a plugin that only waits for `Game` waits forever.
Probes now drive the title screen themselves (`play_campaign`,
`select_level`, `create`, `skip_dialog`), as the engine's own
`data/test/plugin/start-campaign.lua` does. That fix applies to the Windows
probe too.

## Engine location

`agent/coordinator/scenario_launch_selftest.py` resolves the engine in this
order: `WESNOTH_EXECUTABLE`, `WESNOTH_LINUX_ENGINE`, `~/opt/bin/wesnoth-linux`,
then the installed Windows engine. The wrapper at `~/opt/bin/wesnoth-linux`
sets `SDL_VIDEO_DRIVER=offscreen`, `SDL_AUDIO_DRIVER=dummy`, and
`--data-dir` to the 1.19.27 source tree's `data/`.

## Building the engine (no root required)

1. Install micromamba to `~/opt/bin` and create `~/opt/wbuild` from conda-forge
   with: `cmake ninja pkg-config gxx_linux-64=13 gcc_linux-64=13 sdl3
   libboost-devel pango cairo fontconfig freetype libvorbis libogg openssl
   libcurl zlib bzip2 libpng libjpeg-turbo libwebp readline gettext icu expat
   glib harfbuzz` (plus any `*-devel` split packages pkg-config reports).
2. Build and install SDL3_image `release-3.4.6` and SDL3_mixer `release-3.2.4`
   from libsdl-org into `~/opt/wbuild`.
3. Download the `1.19.27` source tag; fetch the pinned `src/modules/lua`
   submodule commit and create `src/modules/lua/.git` (the release tarball
   omits submodules and CMake checks for that path).
4. Configure with `-DENABLE_SERVER=OFF -DENABLE_CAMPAIGN_SERVER=OFF
   -DENABLE_TESTS=OFF -DENABLE_NLS=OFF` and
   `-DCMAKE_EXE_LINKER_FLAGS="-L$HOME/opt/wbuild/lib -Wl,-rpath,$HOME/opt/wbuild/lib"`
   (conda-forge ICU needs the newer `libstdc++` in that directory), then
   `ninja wesnoth`.

## Tools here

- `campaign_sequence_plugin.lua` — enters Campaign I through the title screen
  and plays every scenario's scripted win path through real WML events,
  checking heroes, stash/restore, linger mode, transitions, and in-game saves.
- `run_campaign_sequence.py` — stages an add-on copy in isolated userdata,
  runs the plugin, and writes JSON evidence. `production/validate_package.py`
  uses it as the player-build GUI gate.

A scripted win path proves event wiring, transitions, and carryover. It does
not prove that a human can reach each objective by legal moves or that a
mission is fun; those need route probes and playtesting.
