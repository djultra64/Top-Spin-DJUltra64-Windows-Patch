# Main menu Quit Game investigation

Own investigation: djultra64. This document describes local observations; it contains no original game scripts or assets. No game was launched for this analysis.

The original main menu is defined by `Media/MenuPart/RuiPC/MainMenu.rui`, a ZIP-format archive. `Scenes/newmain.sceneData` is a Lua 5.0 binary chunk defining the scene graph, controls, animation data and action sequences. `Scenes/newmain.scene` is a second Lua chunk defining input events indexed by the same control array. The locally built Lua 5.0.3 interpreter can load both chunks into an isolated table environment for inspection; the chunks examined contain table initialization rather than runtime engine calls. A production patch should verify hashes before evaluating these exact chunks.

## Version guards

| Original input | SHA-256 |
| --- | --- |
| MainMenu.rui | b1a7c37765fd8067db97adbf9a653147b82e1aeaa2e957ff6c3bbdd451d704e3 |
| Scenes/newmain.scene | 7ceece1730c09fb0b3007d6d0eee5610fb1cca015f09b8d648ccabb317d7be00 |
| Scenes/newmain.sceneData | fc0464ecb5d1bfa58e7184c46739aa9d61bbbd4b2b12c10fa1cae4d44bdd08d4 |

The enclosing Base.rui changes legitimately when controller font atlases are installed, so it should not be required or modified for this feature.

## Existing menu structure

The scene's `Graph.Children[2].Children[3]` is the node named `main`. Its children include the original text nodes `pht_exhibition`, `pht_custom_tournament`, `pht_career_mode`, `pht_live`, `pht_tuto_tennisschool`, and `pht_options`, followed by corresponding selection groups using the existing `SelectedText` template. Some rows are conditionally hidden by the original game; the visible Windows/Linux menu currently has five rows.

`SceneData.Controls[150]` is `Exhibition`, associated with `pht_exhibition`. Its Up event selects Options and its Down event selects Custom Tournament. `SceneData.Controls[161]` is `RootOptions`, associated with `pht_options`; AButton and Start invoke `Validation_Options`, Up selects Live, and Down wraps to Exhibition. These bindings pass through the game's existing keyboard/controller action layer.

The action `Selection_Options(sound)` plays the navigation sound, makes `RootOptions` active, and calls the scene's `HighlightSelected` method with `group_options`. The corresponding selection group is `SelectedText5:Menu`; controls 6 and 97 refer to this group and its SelectedText alias. A new row can follow the same structure using unique control and node names.

The Options text's local translation is approximately (-137.62, -103.21); the selection group's local translation is approximately (-134.51, -115.69). The prior rows are spaced about 40–60 local units apart. A final Quit row needs roughly another 40 units and a visual check against the bottom help bar. The original `main` node is animated by the existing `texte_on`/`texte_off` clips, so a new child inherits the menu's overall visibility when entering a submenu. Append new nodes and controls instead of inserting them: existing event indices, animation source clips, ordered names and keyframe blobs must remain valid.

`group_options` and the training group also have dedicated animation tracks. A cloned Quit group should not claim those tracks; its SelectedText template already supplies focus/selection animation. The original Options row must retain its original animation metadata.

The existing English string-table key `ct_quit` already displays `QUIT GAME` in `NovaBlackSSK_14`, size 100. Reusing that key for both the new plain text and the SelectedText content avoids any change to compiled string tables, fonts, textures or translations.

## Shutdown route

The executable contains an existing game-wide quit confirmation with the keys `ask_confirm_quit`, `quit_yes`, and `quit_no`. Their code references are near 0x5b9910–0x5b9b40. The character editor's separate `pc_quit` dialog is near 0x52ebe0 and asks about leaving without saving; it should not be confused with the game-wide quit action.

`PAM_SaveAndQuit` is registered near 0x47e40c but points to 0x4022a0, which only returns false. It is a stub and must not be used as a working shutdown action. The parent investigation owns the exact native confirmation bridge and its calling convention. A UI-only proof does not establish that options are saved or shutdown is correct.

## Proposed patch

1. Verify the original MainMenu archive and both member hashes.
2. Load only those two vetted Lua chunks in a private build tool. Append a Quit text node and SelectedText group under `main`, reusing `ct_quit` and original font/style objects locally; leave existing asset data intact.
3. Append the necessary controls and matching event tables. Link Options Down to Quit, Quit Up to Options, Quit Down to Exhibition, and Exhibition Up to Quit. Preserve the existing cancel/back behavior and Help conventions. Bind AButton and Start to a narrow native bridge that invokes the original game-wide confirmation, without process termination or bypassing normal shutdown.
4. Add a `Selection_Quit` action following the existing sound, active-control and highlight policy. Avoid rebuilding original animation keyframe blobs.
5. Compile the changed tables with the matching Lua 5.0 format, validate the table delta and reload both outputs in an isolated environment. Replace only the two archive members; retain all other ZIP entries and their original metadata, including legacy bad-CRC entries if encountered elsewhere.
6. Keep generated chunks and modified archives private. Public sharing contains only the original patch tool, expected hashes and synthetic tests. Test the final UI once for layout, keyboard/controller navigation, cancellation, confirmation, saved options and graceful exit.

This is a concrete implementation path, not a claim that the new menu or native bridge has been runtime validated. Local inspection artifacts are under ignored `build/quit-investigation/`.

## Implemented private candidate

`tools/menu_quit.py` and `tools/menu_quit.lua` implement the guarded delta. API: `patch_main_menu(raw, lua)` returns the changed archive; `patch_file(source, destination, lua)` requires a separate output. The Lua recipe appends two graph nodes and three controls, adjusts the matching node-type counts, adds two actions, and changes exactly two wrap-navigation bindings. Reloaded tables are normalized by removing only these changes and compared recursively with the original tables. A 40-unit row follows the original four-degree slant without moving individual original rows.

The initial visual test found the new row too low. The revised patch shifts the complete `main` node up 24 local units (about 54 pixels at 1080p). Changing its initial position alone would be overwritten: three original absolute animation tracks address OrderedNames index 11 (the twelfth name, `main`) and contain `translateY=0`. The patch therefore changes the initial Y coordinate and precisely three float fields in `ClipsKeyframeData`, at byte offsets 3016, 3896 and 6312, to 24. The original blob SHA-256 is `9c0f37a928e8f429dc4a97277f777b2f8db2de565c78feb9b43a63f5adfc2239`; both this hash and each node/track structure are checked. The three replaced float slots occupy 12 bytes; six bytes actually differ. Every other animation byte and every original row's relative position remain identical. Reversal of these exact changes is included in the complete semantic comparison.

The first attempted action reused `PAM_SaveAndQuit`, but investigation showed that method is registered for the roster class, not the main-menu scene. The revised action invokes the new main-menu method `this.DjultraQuitGame('djultra64.quit-game')`. The native agent registers this additional method alongside existing main-menu methods and requires the marker before invoking the existing game-wide confirmation. The original Career archive's `Scenes/ct_roster.sceneData`, `Actions.SaveAndQuit`, calls its own `this.PAM_SaveAndQuit()`; that original binding and no-op behavior are retained. Single-quoted string arguments are supported: numerous original main-menu actions use them for TitleSelect, SetGameMode, PushOption, Vibration and CreditsVideo.

The generated candidate is private under `build/quit-mainmenu-candidate/Media/MenuPart/RuiPC/MainMenu.rui`, with verification metadata alongside it. Eighty archive members remain unchanged; only the two vetted main-menu chunks are replaced. Synthetic tests cover exact navigation/action changes, stable original control indices, source/member hash rejection, reapplication rejection, parent/track positioning and ZIP preservation. Matching Lua 5.0.3 compilation and complete table preservation also pass against the actual private archive. The revised layout and native confirmation require the parent's planned integration test.

## Focused runtime validation

The revised private Linux/Proton candidate was tested by the user. They confirmed the raised Quit Game row, removed FPS counter, original confirmation, No cancellation and Yes exit work correctly. The diagnostic recorded `confirmed`; the owned process exited with code 0. The complete source suite passed 145 tests without skips outside the 32-bit syscall filter. Windows executable guards match statically; this is not a new Windows runtime test of the Quit revision.
