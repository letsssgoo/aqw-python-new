# `bot/ultra` — one config file, one class per boss

Everything tunable lives in **`config.py`**. You should be able to fill it in
from this page alone, without reading any of the fight code.

| file | what it is |
|---|---|
| `config.py` | **you edit this.** accounts, gear, per-boss loadouts |
| `core_ultra.py` | shared machinery (`apply_loadout`, `attack_loop`, `finish`, …) + `UltraSpeaker`. No boss logic |
| `ultra_<boss>.py` | one boss each: `class Ultra<Boss>(CoreUltra)` with `run()` |
| `daily.py` | runs the four daily bosses in order (slot 1–4) |
| `grammiel.py` | runs just Gramiel (slot 1–4) |
| `*.bat` | the 2×2 pane launchers — **do not edit**, they only pipe a number in |

---

## Which launcher runs what

| launcher | module | reads from stdin | does |
|---|---|---|---|
| `bot/ultra/ultra_daily_pane.bat` | `py -m bot.ultra.daily` | `1` `2` `3` `4` | Tyndarius → Engineer → Ezrajal → Warden, **one slot each** |
| `bot/ultra/ultra_grammiel.bat` | `py -m bot.ultra.grammiel` | `1` `2` `3` `4` | Gramiel only, one slot each |

The four windows are **four slots of the same run**, not four different bots:
each number picks `ACCOUNTS[n-1]` to log in as *and* `LOADOUTS[boss][n]` to
wear. Slot 1 is also the account the other three follow.

To run one boss standalone instead, point `start.py` / `gui.py` at a module —
`bot.ultra.ultra_warden`, `bot.ultra.ultra_gramiel`, … Each of those exposes
`main(cmd)` and defaults to **slot 1**.

---

## Filling `config.py` by hand

### 1. Accounts

```python
SERVER = "alteon"
ACCOUNTS = [
    AccConfig("name1", "pass1"),
    AccConfig("name2", "pass2"),
    AccConfig("name3", "pass3"),
    AccConfig("name4", "pass4"),
]
```

Order matters — index 0 is what `echo 1 |` selects, and it is the follow leader.

### 2. The four slots

Each boss configures four independent loadouts. They are **roles, not classes**:
a slot's job changes per boss, so the same slot number wears different gear
below.

| slot | Tyndarius | Engineer | Ezrajal | Warden | Gramiel | Drakath |
|---|---|---|---|---|---|---|
| 1 | Quantum Chronomancer | Quantum Chronomancer | Quantum Chronomancer | Legendary Hero | LightCaster | StoneCrusher |
| 2 | Legion Revenant | Legion Revenant | Legion Revenant | Legion Revenant | Obsidian Paladin Chronomancer | Legion Revenant |
| 3 | Lord Of Order | Lord Of Order | Lord Of Order | Lord Of Order | Lord Of Order | Lord Of Order |
| 4 | ArchPaladin | ArchPaladin | ArchPaladin | ArchPaladin | StoneCrusher | ArchPaladin |

`SOLO_LOADOUTS` is separate: it is keyed by **class** rather than slot, because
Ultra Speaker has no slots — it wears whatever `Bot(soloClass=…)` says.

### 3. Gear is an **enhancement name**, not an item name

```python
Loadout(
    cls="Legion Revenant",        # item name
    weapon="Arcana's Concerto",   # ENHANCEMENT name
    helm="Forge",                 # ENHANCEMENT name
    cape="Vainglory",             # ENHANCEMENT name
    scroll="Scroll of Enrage",    # item name
)
```

Only **`cls`** and **`scroll`** are item names. `weapon`, `helm` and `cape`
name the *enhancement* socketed into whatever gear you own. This is why
`Valiance` never appears in your inventory as an item called "Valiance" — it is
the enhancement sitting in a sword called *Blade of the Bound Eclipse*.

The config **field is the slot**: `GEAR_SLOTS` pins `weapon → Weapon`,
`helm → he`, `cape → ba`, so `equip_enhancement` never has to guess. This also
stops gear from overwriting the class, and matters because `Forge` alone sells
24 tiers across three different slots.

### 4. Why the class is still an item name

No enhancement identifies a class — the same enhancement fits many classes.
So `cls` is matched as an item: **inventory first, then the bank** (`equip_item`
walks to the bank and back), and if it is in neither, the bot stops.

### 5. Forge vs basic — and when you need `level=`

| | source file | tiers | `level=` needed? |
|---|---|---|---|
| **forge** (`Valiance`, `Forge`, `Absolution`, `Penitence`) | `forge_enhancement.jsonl` | one or two, at the level cap | no — one name, one tier |
| **basic** (`Awe Blast`, `Wizard Helm Enhancement`, `Mana Vamp`) | `basic_enhancement.jsonl` | one per level, 51–100 | only to pin a tier |

A bare basic name means "whatever tier I own" and matches anything. Pin it only
when you own several tiers and need a specific one:

```python
weapon="Awe Blast"                          # any tier you own
weapon=Enhance("Awe Blast", level=100)      # only the level-100 tier
weapon=Enhance("Awe Blast", level=100, rarity=7)   # level 100 exists at two rarities
```

The `rarity` pin exists because some names ship **two tiers at level 100**
(51 names → 52 entries). If the pin does not match, the lookup returns nothing
and the bot stops rather than equipping the wrong one.

`None` for any gear field means *leave that slot alone*; `scroll=None` leaves
whatever scroll was already on, which is what Engineer / Ezrajal / Warden do.

### 6. Where to get an `EnhID`

```bash
python tools/show_enh.py "Valiance"        # every tier: slot, source, level, rarity, item_id
python tools/show_enh.py                   # all distinct names in both captures
python tools/show_shops.py                 # which shop/file a name came from
python tools/find_item.py "quantum"        # item NAMES in your inventory (classes, scrolls)
```

`item_id` is the value you care about. Note the shop payload's own `EnhID`
field is **always 0** — identity is `ItemID`, which is the same number the
inventory reports as an item's socketed `EnhID`.

To confirm that id is really yours: `python tools/xcheck_basic_enh.py`
cross-checks every socketed `EnhID` in `capture_logs/` against the two shop
captures. The wiki item page also lists Item IDs.

### 7. Verify before you launch

```bash
python tools/check_loadouts.py    # every name resolves? exit 0 = yes
python tools/test_imports.py      # every entry point imports and exposes main/run
python -m compileall -q core model bot templates tools app
```

`check_loadouts` also prints a **non-fatal** list of names your captured
account does not own. That is expected and deliberate: seeing something you
don't have makes `apply_loadout` call `_abort()`, which **stops the bot**
instead of carrying on with whatever happened to be equipped. Nothing retries
— there is no "100% hit" guarantee anywhere in this code, by design.

---

## Editing a boss

Open just its file. Each one documents its role, quest id, map, monster
priority and skill list at the top of the class, so you never have to read the
others:

```python
class UltraWarden(CoreUltra):
    BOSS = "warden"
    QUEST = 8153
    MAP  = "ultrawarden"
```

A boss fight is: `apply_loadout` → `join_and_wait` → `precast_buffs` →
`attack_loop(...)` → `finish(quest)`. If `apply_loadout` returns `None` the
loadout failed, the bot was already stopped, and `run()` returns immediately.

To change *when* it fights, edit the class. To change *what it wears*, edit
`config.py`.
