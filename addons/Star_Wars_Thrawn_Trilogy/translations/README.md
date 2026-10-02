# Translations

`wesnoth-Star_Wars_Thrawn_Trilogy.pot` is the translation template: every
player-facing string in the add-on (`_ "..."` under the
`wesnoth-Star_Wars_Thrawn_Trilogy` textdomain).

To translate, copy it to `<lang>/LC_MESSAGES/wesnoth-Star_Wars_Thrawn_Trilogy.po`
(for example `de/LC_MESSAGES/...`), fill in the `msgstr` entries, and compile
with `msgfmt` to a `.mo` file in the same folder.

Regenerate the template after text changes with
`python3 production/tools/gen_pot.py`.
