---
version: 1
slug: "colosseum-randomizer-gui-py"
primary_target: "orre_randomizer/gui.py"
related_targets: ["orre_randomizer/xd_ui.py", "orre_randomizer/ui_theme.py", "orre_randomizer/ui_workspace.py", "orre_randomizer/ui_bonus_event.py", "orre_randomizer/ui_pokemon_details.py", "orre_randomizer/workspace_copy.py", "orre_randomizer/workspace_i18n.py", "orre_randomizer/ui_home.py", "orre_randomizer/ui_updates.py", "orre_randomizer/update_service.py"]
---

# Surface: Shared game workspaces

Mode: Operate. Preserve the established native Qt menu composition and the
user-approved Colosseum, XD and neutral-home themes. The root DESIGN.md records
the visual system; this brief records the workflow and its states.

Home selects Colosseum or XD. Each game uses **ROM → Settings → Create**, with
shared templates and wording. Simple is the default; Advanced exposes individual
rules without resetting values. Profiles, language and independent music/sound
controls stay in the header. The six languages are FR, EN, DE, ES, IT and JA;
unsupported system languages fall back to English.

| Surface commitment | Implementation |
| --- | --- |
| Three persistent steps | Shared wizard frame; active step includes the Poké Ball cursor |
| Game-specific identity | Original game logo, theme and bundled interface media; neutral home gradient |
| Home update | One neutral secondary button below both tiles for newer verified stable Windows releases; downloads, verifies, applies and restarts, with inline progress/cancel/error states |
| Settings views | Configuration and Pokémon preview share the seed row |
| Three presets | Pokémon + moves, Pokémon only, Unchanged copy; explanations appear directly below |
| Custom values | Clearly identified; Simple/Advanced switches preserve them |
| Advanced rules | Searchable metadata, shared control order and category help; 192 px sidebar or compact selector |
| Preview tabs | Colosseum: 2 starters, 48 Shadows, 4 gifts and optional-event preview; XD: 1 starter, 83 Shadows, 7 gifts, 9 Poké Spot slots |
| Pending preview | Native originals and unknown replacements; resolved fixed/manual encounters show their portraits and sheets, with a red star only for a known shiny |
| Search and scrolling | Names in six languages and National Pokédex IDs; visible-range counter and contrasted scrollbar |
| Loading | Shared background worker, 115 ms cosmetic cycle, progress, cancellation and stale-result rejection |
| Current preview | Final seeded results, up-to-date state and optional duplicate-family tab |
| Pokémon sheets | Single-click access; shared Summary, Moves and Evolutions tabs, portraits and raised red shiny star |
| Creation | Applied settings with values/units, ISO/RVZ output, shared DolphinTool path and original preservation |
| Report import | Restores seed/rules without replacing paths and compares the selected original |
| Progress and results | Shared creation-only Details disclosure, cancellation, stage log, output folder, JSON report and offline journal |

Both randomizing presets draw from all starter stages without power, type or
value matching and randomize abilities. Legendary and Mythical species are
excluded from replacement draws; fixed legendary encounters remain. Original
shop Balls are preserved. Pokémon only retains moves, TMs and ordinary items;
Pokémon + moves randomizes those too. Accessible evolutions and family diversity
are shared defaults.

Starters, gifts and supported trainer/Shadow encounters use a seeded 5% shiny
rate. XD's Shadow unlock is a separate control; wild Poké Spots instead roll a
fresh 5% chance for each new encounter, visible before battle. A preview cannot
predict that wild roll at an intermediate rate. Native starter-pair, event-gift,
trade and scenario restrictions retain game-specific help. Imported profiles
keep saved values; selecting a preset applies the current defaults.

Keep navigation visible at 680 × 540 and check 1040 × 800 as well. Scroll only
the active form or result area. Common copy comes from workspace_copy.py,
workspace_i18n.py and shared option metadata; do not introduce per-game synonyms.
See docs/INTERFACE_PARITY.md for the shared behavior and intentional exceptions.

Verification covers all six languages, both sizes, pending/loading/ready/error
states, search, cancellation, preserved values, report comparison and sheets.
Native ROM and save files remain outside the interface-maintenance workflow.
The Events preview reuses the existing portrait and Pokémon-sheet controls.
Its bonus event can be toggled without leaving the preview; pending random
members show question marks; resolved fixed members show their actual portraits
and sheets. The known bonus species uses XD's original dark portrait or its
matching shiny variant. Ready teams come from the production patch plan,
including shiny decisions. Cards use three columns on a wide panel and two on
smaller windows, inside one clearly scrollable content area. Keep a 12 px gap
between each portrait and its text, then 8 px before the sheet button.
Validation errors must not reveal the creation log. Details becomes available
only after generation starts and only on Create, including its resulting failure
or cancellation. A new attempt clears the old log and resets the disclosure.

Home keeps game selection primary. Its optional release update sits below
the two tiles and above the credit, with the same neutral palette as header
controls. The localized version label also serves as its accessible name.
The once-per-session asynchronous check has no modal or visible loading row;
current, offline, failed and invalid responses leave the button hidden.
One click downloads, verifies, applies and restarts the app. Downloading is
cancellable; preparation and restart explain what happens next. Errors show
inline and allow retry. Source checkouts do not replace themselves. Returning
home retains an already available update without starting another check.

The application header stays visible while one home-body area scrolls vertically
when needed. Tiles stack below 800 px and sit side by side otherwise; the tiles,
download and credit share this scroll area. Do not add a nested update scroller
or a horizontal scrollbar. Existing shared content bounds remain 1,200 px.
