# Knowledge — Menulis Script Bot AQW (script mode)

> Pendamping `knowledge.md`. `knowledge.md` menjelaskan **arsitektur engine**;
> file ini menjelaskan **cara menulis bot/script** memakai pola yang sudah
> terbukti jalan di repo ini:
> `bot/darkon_mats/`, `bot/LR/`, `bot/ultra/`, `bot/templeshrine/`.
>
> Tujuan praktisnya: **porting bot dari client AQW lain (C# / Flash) ke engine
> Python ini.** Karena semua bot AQW bicara protokol server yang sama, porting
> itu 1:1 di level aksi — bukan tafsir ulang gameplay. Lihat §11.

---

## 0. Cara memakai dokumen ini

1. Baca §1–§3 sekali untuk tahu bahan-bahannya.
2. Cari pola yang paling mirip dengan bot sumber Anda di §5–§9, copy strukturnya.
3. Ikuti playbook porting di §11 sambil membuka tabel terjemahan di sana.
4. Sebelum bilang selesai, jalankan checklist §13.

Yang **tidak** perlu dibaca lagi: `commands/` (itu mode queue, bukan script).
Script mode tidak memakai kelas `*Cmd` sama sekali.

---

## 1. Model mental: dua cara menjalankan bot

Engine punya dua mode. Untuk porting bot pihak ketiga, hampir selalu yang
benar adalah **script mode**.

| | Queue mode (`bot_cmds/`) | **Script mode (`bot/`)** |
|---|---|---|
| Ditulis sebagai | daftar objek `*Cmd` + label/index | satu `async def main(cmd)` |
| Cocok untuk | alur linier pendek, GUI | logika kompleks, loop, state, multi-akun |
| Flag | `isScriptable=False` | **`isScriptable=True`** |
| Dipanggil | `asyncio.run(bot.start_bot())` | `asyncio.run(bot.start_bot(main))` |

### Siklus hidup script mode (`core/bot.py::start_bot`)

1. `Bot(...)` dibuat, `bot.set_login_info(user, pass, server)`.
2. `asyncio.run(bot.start_bot(main))` → HTTP login → socket TCP → handshake Flash.
3. Task `read_server_in_background()` jalan, pesan server di-dispatch ke
   `bot.handle_server_response()`.
4. Engine menunggu `is_char_load_complete` (dari packet `loadInventoryBig`),
   lalu menyalakan task auto-quest, lalu **`await main(cmd)`**.
5. **Begitu `main` `return`, `bot.stop_bot()` dipanggil.** Artinya: script yang
   harus jalan terus memakai `while cmd.is_still_connected():` di dalam `main`,
   atau diakhiri `await cmd.sleep(100000)` (lihat `UltraSpeaker.run`).

`main` boleh menerima `cmd: Command` (konvensi sekarang) **atau** `bot: Bot`
(konvensi lama). `Bot._resolve_script_arg()` membedakan dari nama/annotation
parameter pertama: kalau namanya `bot` atau di-annotate `Bot`, yang dikirim
objek `Bot`. Script baru: pakai `main(cmd: Command)`.

---

## 2. Kerangka minimum

### File paling kecil yang bisa dijalankan

Contoh nyata: `bot/darkon_mats/a_melody.py`

```python
from bot.darkon_mats.core_darkon_mats import a_melody
from core.bot import Bot
from core.command import Command

async def main(cmd: Command):
    await a_melody(cmd, 300)
```

File itu lalu dijalankan sebagai `BOT_PATH` (`bot.darkon_mats.a_melody`) lewat
`start.py` / `.env`, atau langsung:

```python
if __name__ == "__main__":
    import asyncio
    bot = Bot(itemsDropWhiteList=whitelist, cmdDelay=600, showDebug=True,
              autoRelogin=True, isScriptable=True)
    login = input("Login (username,pass): ").split(",")
    bot.set_login_info(login[0], login[1], "Safiria")
    asyncio.run(bot.start_bot(main))
```

Contoh nyata pola itu: `bot/void_aura.py`, `bot/LR/leto_spp.py`.

### Aturan nama (kontrak string)

- `BOT_PATH` di `.env` / `.bat` adalah **string**, bukan import. Kalau modul
  diganti nama, grep string-nya dulu.
- Setiap modul yang disebut `.bat`/`.env` **wajib** mengekspos `main(cmd)`.
- Modul `daily.py` / `grammiel.py` beda: `main(cmd)` ada, tapi runner sebenarnya
  juga bisa dipanggil sebagai `py -m bot.ultra.daily` (lihat §8).

### Konvensi repo

- `async` di semua I/O; predicate/tanya-state = fungsi sinkron.
- Di dalam script pakai `cmd.sleep(ms)`, **jangan** `asyncio.sleep`.
- Log lewat `print` yang sudah dipakai semua bot (import `colorama.Fore` untuk
  warna) — engine tidak punya logger khusus.
- Nama file folder: `snake_case`; kelas: `PascalCase`.

---

## 3. Cheatsheet API `Command`

Semua yang penting untuk menulis script. `async` kecuali ditandai **sync**.

### Koneksi & util
| Panggilan | Catatan |
|---|---|
| `cmd.is_still_connected()` **sync** | guard wajib tiap loop |
| `await cmd.sleep(ms)` | jeda non-blocking |
| `await cmd.send_packet(packet)` | paket mentah (lihat §4) |
| `await cmd.send_chat(msg)` | zone chat |
| `await cmd.rest()` | restRequest (regenerasi) |
| `cmd.stop_bot(msg="")` **sync** | tutup koneksi, akhiri sesi |
| `cmd.subscribe(cb)` / `cmd.unsubscribe(cb)` | baca **setiap** pesan server (§9) |
| `cmd.get_player()` **sync** | objek `Player` mentah |

### Quest
| Panggilan | Catatan |
|---|---|
| `await cmd.ensure_accept_quest(qid)` | accept sampai tercatat in-progress |
| `await cmd.ensure_turn_in_quest(qid, item_id=-1, amount=1)` | turn-in sampai lepas dari in-progress |
| `await cmd.accept_quest(qid)` / `await cmd.turn_in_quest(qid, item_id=-1, qty=1)` | sekali tembak |
| `cmd.can_turnin_quest(qid)` **sync** | butuh item-nya ada (cek inventory+temp) |
| `cmd.quest_in_progress(qid)` / `cmd.quest_not_in_progress(qid)` **sync** | |
| `await cmd.register_quest(qid)` | auto accept+turn-in latar (`handlers/register_quest.py`) |
| `await cmd.is_green_quest(qid)` / `await cmd.is_completed_before(qid)` | satu kali **tembakan turn-in** (`ccqr`), lalu baca penolakannya. `bSuccess=1` → keduanya True; `"Missing Turn In Item"` → hijau saja (quest terbuka, belum selesai); `"Missing Quest Progress"` → keduanya False; `"One Time Quest Only"` → selesai saja. **Hijau ≠ sudah selesai** — quest one-time yang sudah selesai justru hijau=False (dikunci `tools/test_quest.py`) |

### Item / shop / bank
| Panggilan | Catatan |
|---|---|
| `cmd.is_in_inventory(name, qty=1, operator=">=", isTemp=False)` **sync** | nilai di-`normalize()` |
| `cmd.is_in_bank(name, qty=1, operator=">=")` **sync** | |
| `cmd.get_quant_item(name)` **sync** | qty di inventory |
| `await cmd.bank_to_inv(name_or_list)` / `await cmd.inv_to_bank(name_or_list)` | |
| `await cmd.equip_item(name)` | inventory→bank→equip; `False` = tak ada |
| `await cmd.equip_scroll(name, item_type=ScrollType.SCROLL)` | wajib sebelum `use_skill(5, …)` |
| `await cmd.equip_enhancement(name, slot=None, *, level=None, rarity=None)` | pilih gear dari nama enhancement |
| `await cmd.buy_item(shop_id, item_name, qty=1)` | shop auto-load kalau belum |
| `await cmd.ensure_load_shop(shop_id)` / `await cmd.sell_item(name, qty=1)` | |
| `await cmd.get_map_item(map_item_id, qty=1)` | ambil map item (drop di tanah) |
| `cmd.add_drop(name_or_list)` **sync** | daftar drop yang auto-diambil |
| `cmd.farming_logger(item, target_qty=1, is_temp=False)` **sync** | cetak progres |

### Navigasi
| Panggilan | Catatan |
|---|---|
| `await cmd.join_map(map_name, roomNumber=None, safeLeave=True)` | room privat = angka unik |
| `await cmd.join_house(house_name)` | |
| `await cmd.jump_cell(cell, pad)` | pindah cell/pad |
| `await cmd.walk_to(x, y, speed=8)` | jalan ke koordinat (dipakai Speaker) |
| `await cmd.goto_player(name)` | ikut pemain lain |
| `await cmd.jump_to_monster(name)` | lompat ke cell monster |
| `await cmd.leave_combat(safeLeave=True)` | keluar combat (+ balik ke Enter/Spawn) |
| `cmd.is_in_map(name)` / `cmd.is_not_in_map(name)` / `cmd.is_not_in_cell(cell)` **sync** | |

### Combat
| Panggilan | Catatan |
|---|---|
| `await cmd.use_skill(index=0, target_monsters="*", hunt=False, skill_mode=SkillMode.ALL, reload_delay=700, *, buff_only=False) -> bool` | `0` = auto-attack, `5` = scroll |
| `await cmd.use_next_skill(skill_list, target_monsters="*", hunt=False) -> bool` | pilih slot yang siap (disarankan) |
| `await cmd.wait_use_skill(index, target_monsters="*")` | tunggu cooldown lalu cast |
| `cmd.is_monster_alive(name="*")` **sync** | hidup di cell sekarang |
| `cmd.get_monster_hp(name)` / `cmd.get_monster_hp_percentage(name)` **sync** | `-1` = tak ketemu |
| `cmd.get_monster(name)` **sync** | objek `Monster` |
| `cmd.hp_below_percentage(pct)` **sync** | HP sendiri |
| `cmd.start_aggro(mon_ids, delay_ms=500)` / `cmd.start_aggro_by_cell(cells)` / `cmd.stop_aggro()` **sync** | auto re-aggro berulang |
| `cmd.check_is_skill_safe(slot)` **sync** | gate HP per kelas (VHL/SSoT/DoT/Healer) |

`SkillMode`: `ALL=3`, `ATTACK_ONLY=2`, `BUFF_ONLY=1`, `NONE=4`.
`skill_mode` menentukan cast apa yang boleh keluar; `buff_only=True` = shorthand
`BUFF_ONLY`. Dipakai antara lain untuk "jangan heal saat kena debuff damage
terbalik" (lihat `core_temple.py` memakai `test` aura `Sun's Heat`).

### Player / party
| Panggilan | Catatan |
|---|---|
| `cmd.get_equipped_class()` / `cmd.get_farm_class()` / `cmd.get_solo_class()` **sync** | item kelas terpasang / dari `Bot(...)` |
| `cmd.get_player_cell()` / `cmd.get_player_pad()` / `cmd.get_player_position_xy()` **sync** | |
| `cmd.wait_count_player(n)` / `cmd.wait_count_player_in_cell(cell, n)` **sync** | jumlah pemain |
| `cmd.get_player_in_map(name)` / `cmd.is_player_in_cell(name, cell)` **sync** | pemain lain |
| `cmd.get_followed_player()` / `cmd.get_slaves()` **sync** | dari `Bot(followPlayer=…, slavesPlayer=…)` |
| `cmd.get_user_id()` **sync** | id kita di cell (dipakai filter packet) |

`Player` mentah (via `cmd.get_player()`): `CELL`, `PAD`, `CURRENT_HP`, `MAX_HP`,
`MANA`, `IS_IN_COMBAT`, `ISDEAD`, `INVENTORY`, `TEMPINVENTORY`, `BANK`,
`FACTIONS`, `SKILLS`, `AURAS`, `X`, `Y`, `GOLD`, `EXPFARMED`.
Predikat berguna: `hasAura(name)`, `getAura(name)`, `canUseSkill(slot)`,
`is_hp_below(pct)` (untuk `PlayerArea`).

`bot` mentah (via `cmd.bot`): `areaId`, `strMapName`, `monsters`,
`player_in_area`, `user_ids`, `username_id`, `deaths` (penghitung mati),
`is_paused` / `is_script_paused` (dipakai GUI), `items_drop_whitelist`,
`player`, `add_drop`, `start_battle_analyzer()` / `stop_battle_analyzer()`.

---

## 4. Paket mentah (kalau API belum menutupi)

Semua paket keluar adalah string `%xt%zm%…%` (zone) atau XML handshake.
Yang sudah dipakai bot di repo ini:

| Keperluan | Paket |
|---|---|
| Skill → monster | `%xt%zm%gar%1%0%a{slot}>m:{id1},{id2}%wvz%` |
| Skill → pemain/self | `%xt%zm%gar%1%0%a{slot}>p:{uid}%wvz%` |
| Scroll (slot 5) | `%xt%zm%gar%1%0%i1>m:{id}…%{scroll_id}%wvz%` |
| Potion | `%xt%zm%gar%1%0%i1>p:{uid}%{potion_id}%wvz%` |
| Pindah cell | `%xt%zm%moveToCell%{areaId}%{cell}%{pad}%` |
| Jalan | `%xt%zm%mv%{areaId}%{x}%{y}%{speed}%` |
| Ganti map | `%xt%zm%cmd%1%tfer%{user}%{map}[-{room}]%` |
| Ikut pemain | `%xt%zm%cmd%1%goto%{name}%` |
| Masuk house | `%xt%zm%house%1%{houseName}%` |
| Chat | `%xt%zm%message%{areaId}%{msg}%zone%` |
| Aggro | `%xt%zm%aggroMon%{areaId}%{id1}%…%` |
| Respawn | `%xt%zm%resPlayerTimed%{areaId}%{user_id}%` |
| Accept quest | `%xt%zm%acceptQuest%{areaId}%{qid}%` |
| Turn in quest | `%xt%zm%tryQuestComplete%{areaId}%{qid}%{item_id}%false%{qty}%wvz%` |
| Load / beli / jual | `%xt%zm%loadShop%…%` / `%xt%zm%buyItem%…%` / `%xt%zm%sellItem%…%` |
| Bank | `%xt%zm%bankToInv%…%` / `%xt%zm%bankFromInv%…%` |
| Equip item | `%xt%zm%equipItem%{areaId}%{item_id}%` |
| Equip scroll/potion | `%xt%zm%geia%{areaId}%{item_type}%{s_meta}%{item_id}%` |
| Ambil map item | `%xt%zm%getMapItem%{areaId}%{map_item_id}%` |
| Ambil drop | `%xt%zm%getDrop%{user_id}%{item_id}%` |
| **Dungeon queue** | `%xt%zm%dungeonQueue%25127%{map}%` |
| **Party invite** | `%xt%zm%gp%1%pi%{username}%` |
| **Party accept** | `%xt%zm%gp%1%pa%{pid}%` |
| Rest | `%xt%zm%restRequest%1%%` |

Paket masuk yang paling sering dibaca script:
`{"t":"xt","b":{"r":…,"o":{"cmd":…}}}`. `cmd` penting: `ct` (combat tick:
HP, `m` monster, `a` aura, `anims` telegraph, `sarsa` damage, `sara` hit/heal),
`pi` (party invite id), `moveToArea`, `loadInventoryBig`, `sAct`, `uotls`,
`mtls`, `event` (mis. `args.zoneSet`), `addItems`, `dropItem`, `ccqr`.

Baca paket lewat `cmd.subscribe(handler)` (handler **sinkron**), lihat §9.

---

## 5. Pola #1 — Farm satu item / kumpulan material

Ini pola terpenting dan paling sering dipakai. Rujukan: seluruh
`bot/darkon_mats/core_darkon_mats.py` dan `bot/LR/core_lr.py`.

### Kerangka satu fungsi farm

```python
async def a_melody(cmd: Command, qty: int = 300):
    item_name = "A Melody"
    map_name  = "astraviajudge"

    # 1. tarik dari bank kalau ada (biar progres lama tak hilang)
    if cmd.is_in_bank(item_name):
        await cmd.bank_to_inv(item_name)

    # 2. cetak progres
    cmd.farming_logger(item_name, qty)

    # 3. sudah cukup? simpan ke bank lalu keluar
    if cmd.is_in_inventory(item_name, qty, ">="):
        await cmd.inv_to_bank(item_name)
        return

    # 4. masuk map
    if cmd.is_not_in_map(map_name):
        await cmd.join_map(map_name)

    # 5. daftarkan drop agar otomatis diambil
    cmd.add_drop(item_name)

    # 6. daftar material yang dibutuhkan
    item_to_farm = [
        {"item_name": "Brass",  "qty": 10, "map_name": map_name, "cell": "r3",  "pad": "Left"},
        {"item_name": "Sinew",  "qty": 10, "map_name": map_name, "cell": "r2",  "pad": "Left"},
        {"item_name": "Knight's Favor", "qty": 1, "map_name": map_name,
         "cell": "r11", "pad": "Right", "is_solo": True},
    ]

    # 7. loop quest sampai item cukup
    while cmd.is_still_connected():
        if cmd.is_in_inventory(item_name, qty, ">="):
            break
        await cmd.ensure_accept_quest(8396)
        await farm_mats(cmd, item_to_farm)
        await cmd.ensure_turn_in_quest(8396)

    await cmd.inv_to_bank(item_name)
```

### `farm_mats()` — helper yang di-copy tiap folder

Ada di `core_darkon_mats.py` **dan** `core_lr.py` (sengaja, tiap folder
mandiri). Fungsinya: pilih kelas (farm vs solo) lalu panggil `hunt_item`.

```python
async def farm_mats(cmd: Command, item_to_farm: list[dict]):
    for item in item_to_farm:
        if not cmd.is_still_connected():
            return
        if item.get("is_solo", False):
            cls = cmd.get_solo_class()
        else:
            cls = cmd.get_farm_class()
        if cls:
            await cmd.equip_item(cls)
        await hunt_item(
            cmd=cmd,
            item_name=item["item_name"],
            item_qty=item["qty"],
            cell=item["cell"], pad=item["pad"],
            map_name=item["map_name"],
            farming_logger=True,
            is_temp=True,          # material quest biasanya masuk temp inventory
        )
```

### Skema dict `item_to_farm`

| key | wajib | arti |
|---|---|---|
| `item_name` | ya | nama item yang di-farm |
| `qty` | ya | target jumlah |
| `map_name` | ya | map tujuan |
| `cell` / `pad` | disarankan | posisi farm; kalau kosong pakai mode hunt monster |
| `is_solo` | tidak (default `False`) | pakai `soloClass` bukan `farmClass` |
| `monster_name` | tidak | target spesifik (default `"*"`) |

`hunt_item` (`templates/hunt.py`) sendiri sudah melakukan: tarik dari bank →
berhenti kalau qty cukup → `add_drop(item)` → loop masuk map → loop ke cell →
loop combat sampai qty cukup (pakai `use_next_skill`, kecuali Chrono Shadow yang
pakai urutan tetap). Karena itu **aman dipanggil berulang** — dia no-op kalau
target sudah terpenuhi.

### `hunt_item` — parameter penuh

```python
await hunt_item(
    cmd,
    item_name, item_qty,
    map_name,
    cell=None, pad="Left", room_number=None, monster_name="*",
    most_monster=False,
    farming_logger=False, hunt=False,
    skill_list=[0,1,2,0,3,4],   # DEFAULT_SKILL_LIST
    is_temp=False,
)
```

`is_temp=True` **wajib** untuk item quest (masuk temp inventory).
`room_number` untuk room privat. `most_monster=True` memilih cell dengan
monster terbanyak.

### Template lain di `templates/hunt.py`

| Fungsi | Untuk |
|---|---|
| `hunt_item(...)` | farm satu item sampai qty |
| `kill_quest(cmd, quest_id, map_name, monster_name, …)` | accept → bunuh sampai `can_turnin` → turn-in |
| `quest_item_req` / `attack_script` | potongan siap pakai untuk quest |
| `hunt_monster_quest_temp_item(...)` | bangun **queue** (mode queue), bukan script |

`templates/story.py` (`do_story_quest`, `QuestItemReq`, `QuestMapItemReq`,
`QuestSingleReq`) juga menghasilkan **queue**, bukan script mode.

---

## 6. Pola #2 — Quest loop (kill → turn in)

Bentuk paling umum, dipakai berkali-kali di `darkon_mats`/`LR`:

```python
while cmd.is_still_connected():
    if cmd.can_turnin_quest(QUEST):
        await cmd.ensure_turn_in_quest(QUEST)
        break
    await cmd.ensure_accept_quest(QUEST)
    await cmd.jump_to_monster("Monster Name")
    await attack_script(cmd, "Monster Name")   # satu tick skill
```

Atau yang lebih ringkas untuk "bunuh sampai quest selesai":
`await kill_quest(cmd, quest_id, map_name, monster_name)` dari
`templates/hunt.py`.

### Loop skill: round-robin vs scheduler

- Round-robin klasik (dipakai `bot/ultra/core_ultra.py::attack_loop` dan
  `core_temple.py`): `skill_list = [0,1,2,0,3,4]`, `index = (index+1) % len`,
  `await cmd.sleep(100..250)` tiap tick.
- Scheduler (disarankan): `await cmd.use_next_skill(skill_list, monster, hunt)`
  — memilih slot yang **siap sekarang**, dan tidur persis sampai cooldown
  berikutnya. Ini yang dipakai `hunt_item` dan `attack_script`; menghindari
  ribuan percobaan yang ditolak server (lihat `SKILL_ANALYSIS.md`).

Gunakan round-robin hanya kalau urutan penting (mis. Chrono Shadow) atau ada
state machine (taunt/finisher) yang butuh kontrol per-tick.

---

## 7. Pola #3 — Class-per-boss + config (bot/ultra)

Kalau bot baru punya beberapa musuh dengan gear/rotasi berbeda, tiru struktur
`bot/ultra` — ini pola paling scalable di repo.

```
bot/ultra/
├── config.py          # SEMUA yang diubah manusia: akun + loadout per boss
├── core_ultra.py      # mesin bersama (CoreUltra) — tanpa logika boss
├── ultra_<boss>.py    # class Ultra<Boss>(CoreUltra): hanya "kapan & bagaimana"
├── daily.py           # jalankan 4 boss berurutan, satu slot per pane
├── grammiel.py        # jalankan 1 boss
└── *.bat              # launcher yang meng-pipe slot 1..4
```

### `config.py` — data, bukan kode

- `ACCOUNTS: list[AccConfig(username, password, server)]`
- `LOADOUTS[boss][slot] -> Loadout(cls, weapon, cape, helm, scroll, monster_prio, kill_order)`
- `GEAR_SLOTS = {"weapon": "Weapon", "helm": "he", "cape": "ba"}`
- `SOLO_LOADOUTS[class_name] -> Loadout` (untuk bot tanpa slot, mis. Speaker)

Aturan penting: **gear ditulis sebagai nama enhancement**, kecuali `cls` dan
`scroll` yang item name. `weapon`/`helm`/`cape` = enhancement yang tersocket
(mis. `"Valiance"`, `"Forge"`, `"Penitence"`). Pakai `Enhance("Awe Blast",
level=100)` untuk mem-select tier. Field `None` = "biarkan slot apa adanya".

### `CoreUltra` — mesin bersama

| Metode | Kerja |
|---|---|
| `apply_loadout(boss)` | equip class → gear (enhancement) → scroll; **gagal = stop bot** |
| `join_and_wait(map)` | masuk room privat + tunggu 4 pemain (+ barrier) |
| `precast_buffs(skills=(1,2,3), buff_only=True, gap_ms=1000)` | buff sebelum pull |
| `attack_loop(skill_list, monster, monster_prio, heal_below, heal_skill, on_tick=…)` | rotasi + heal + hook |
| `finish(quest, spawn=True, unsubscribe=False)` | jump Enter → `yulgar` → `rest()` |
| `message_handler(msg)` / `_on_counter_attack(data)` | reaksi telegraph (§9) |
| `fight_until_party_ready(quest, fight)` | loop sampai semua pane pegang item |
| `restart_pull` / `regroup_at_enter` / `wait_for_boss` | pemulihan setelah wipe |

Fail loud: `_abort()` mencetak merah, menulis log, memanggil `cmd.stop_bot`.
`apply_loadout` mengembalikan `None` ⇒ caller `return` langsung.

### Bentuk satu boss (`ultra_warden.py`)

```python
class UltraWarden(CoreUltra):
    BOSS = "warden"; QUEST = 8153; MAP = "ultrawarden"; BOSS_CELL = "r2"

    async def run(self) -> None:
        loadout = await self.apply_loadout(self.BOSS)
        if loadout is None:
            return
        await self.cmd.accept_quest(self.QUEST)
        await self.join_and_wait(self.MAP)
        await self.precast_buffs()
        await self.cmd.jump_cell("r2", "Left")

        async def fight() -> None:
            await self.attack_loop([0,1,2,0,3,4], monster="Ultra Warden",
                                   monster_prio=loadout.monster_prio,
                                   heal_below=5, heal_skill=2, on_tick=warden_tick)

        await self.fight_until_party_ready(self.QUEST, fight)
        await self.finish(self.QUEST)

async def main(cmd: Command) -> None:
    await UltraWarden(cmd, 1).run()     # standalone = slot 1
```

`on_tick` = hook async per-tick (Warden memakainya untuk finisher saat HP boss
< 600k). Pola ini cara paling bersih menambahkan logika "kalau X maka cast Y".

### Runner multi-slot (`daily.py`)

```python
class DailyUltra:
    async def run(self):
        for step in (self.step_tyndarius, self.step_engineer,
                     self.step_ezrajal, self.step_warden):
            await step()
            if self.aborted:
                return

if __name__ == "__main__":
    slot = int(input("Select bot [1-4] : "))
    b = Bot(roomNumber=9099, isScriptable=True,
            followPlayer=ACCOUNTS[0].username.lower(),
            slavesPlayer=[a.username for i, a in enumerate(ACCOUNTS) if i != 0],
            muteSpamWarning=True)
    b.set_login_info(ACCOUNTS[slot-1].username, ACCOUNTS[slot-1].password, SERVER)
    async def run_bot(cmd): await main(cmd)
    asyncio.run(b.start_bot(run_bot))
```

Setiap pane = **proses terpisah**, satu akun, satu slot — begitulah `.bat`
meluncurkannya. (Alternatif single-proses untuk beberapa akun ada di
`start_multi_env.py` lewat `asyncio.gather`, tapi pola boss/party memilih proses
terpisah karena lebih tahan gagal.)

---

## 8. Pola #4 — Multi-akun & party

Dipakai `bot/templeshrine/*` dan `bot/ultra/party.py`. Semua lewat **file
marker lintas-proses**; engine sendiri tidak punya koordinasi antar akun.

### Bot(...) untuk party

```python
b = Bot(
    roomNumber=9099,
    isScriptable=True,
    followPlayer=slaves[0].username.lower(),   # master
    slavesPlayer=[s.username for i, s in enumerate(slaves) if i != 0],
    respawnCellPad=["Enter", "Spawn"],
    itemsDropWhiteList=["Fragment of Midnight", "Ecliptic Offering"],
    farmClass=selected.char_class,
)
```

- `followPlayer` = akun yang diikuti (master).
- `slavesPlayer` = daftar untuk invite (`get_slaves()`).
- `roomNumber` = room privat bersama.

### Master vs slave (`core_temple.py`)

```python
# master
await cmd.join_map("yulgar", roomNumber=999999)
while not cmd.wait_count_player(4):
    await cmd.sleep(100)
for slave in cmd.bot.slaves_player:
    await cmd.send_packet(f"%xt%zm%gp%1%pi%{slave}%")   # invite
    await cmd.sleep(500)
await self.enter_dungeon()

# slave
while self.pid is None and cmd.is_still_connected():   # tunggu packet "pi"
    await cmd.goto_player(cmd.bot.follow_player)
    await cmd.sleep(1000)
await cmd.send_packet(f"%xt%zm%gp%1%pa%{self.pid}%")   # accept
```

`self.pid` diisi di `msg_handler` saat packet `cmd == "pi"`.

### Dungeon queue

```python
await cmd.send_packet(f"%xt%zm%dungeonQueue%25127%{self.temple}%")
while cmd.is_not_in_map(self.temple) and cmd.is_still_connected():
    await cmd.sleep(200)
```

### Koordinasi lintas-proses (`bot/ultra/party.py`)

Pola ini dipakai kalau empat pane harus sinkron (mis. turn-in serentak, deteksi
party wipe). **Nonaktif kecuali env `AQW_RUN_ID` di-set** (dilakukan `.bat`),
jadi bot manual tidak menunggu party yang tidak ada.

| Fungsi | Kerja |
|---|---|
| `enabled()` | cek `AQW_RUN_ID` |
| `report(boss, round, slot, ok)` / `wait(boss, round, slots)` | verdict per round |
| `barrier(name, key, size, timeout)` | rendezvous sekali (mis. sebelum pull) |
| `report_death` / `death_times` / `clear_death` | deteksi party wipe |
| `mark_done` / `all_done` | pane selesai semua sebelum berhenti |
| `mark_abort` / `any_abort` | gagal preflight supaya tak relaunch ke gagal sama |

State = file JSON di `capture_logs/ultra/<run_id>/party/`.

Agar script Anda sendiri aman untuk 1 proses **dan** 4 proses: bungkus semua
koordinasi dengan `if party.enabled(): …`, dan sisakan jalur "single bot =
langsung jalan".

---

## 9. Pola #5 — Reaksi ke pesan server (telegraph / state machine)

Kalau bot harus bereaksi ke apa yang dikatakan boss (counter attack, "prepare
gather", phase), pakai `subscribe`:

```python
class MyBot:
    def __init__(self, cmd: Command):
        self.cmd = cmd
        self.force_taunt = False
        cmd.subscribe(self.message_handler)   # handler SINKRON

    def message_handler(self, message):
        if not message or not is_valid_json(message):
            return
        try:
            data = json.loads(message)["b"]["o"]
        except Exception:
            return
        if data.get("cmd") != "ct":
            return
        for anim in data.get("anims") or []:
            msg = anim.get("msg")
            if msg and "gather" in msg.lower():
                self.force_taunt = True           # set flag saja

    async def run(self):
        while self.cmd.is_still_connected():
            if self.force_taunt:
                await self.cmd.use_skill(5, "Target")
                self.force_taunt = False
                continue
            await self.cmd.use_skill(0, "Target")
            await self.cmd.sleep(100)
```

Aturan:

- **Handler sinkron.** Jangan `await` di dalamnya; cukup set flag / state.
  Loop utama yang bertindak.
- Handler menerima **semua** pesan mentah, bukan cuma `ct`; filter sendiri.
- Selalu `cmd.bot.unsubscribe(handler)` saat selesai (lihat `finish()` /
  `UltraSpeaker.run`).
- Untuk aksi tertunda: `asyncio.create_task(delayed_taunt())` dengan
  `await asyncio.sleep(5)` **di dalam task** (dipakai `core_temple.py` /
  `core_eclipse.py`) — ini satu-satunya tempat `asyncio.sleep` wajar di script.
- Telemetry/logging juga bisa mengait ke `bot.handle_server_response` (lihat
  `bot/ultra/telemetry.py`), tapi itu berat; untuk script biasa cukup
  `subscribe`.
- Contoh riil: `ultra_ezrajal` (counter attack), `ultra_gramiel` (taunt
  crystal), `core_temple` (`Sun's Warmth` → taunt), `core_eclipse`
  (`converges`, parity taunt).

---

## 10. Logging & observability

| Alat | Kapan | Catatan |
|---|---|---|
| `cmd.farming_logger(item, qty)` | progress farm | cetak `[inv] item x/y` berwarna |
| `bot.debug(*args)` | tracing | hanya kalau `showDebug=True` |
| `print(Fore.X + … + Fore.RESET)` | log biasa | konvensi seluruh repo |
| `ultralog.FightLog` | audit per-akun | file `logs/ultra/<akun>.log`, tak pernah raise |
| `telemetry.py` | analisa pasca-run | JSONL, **gated** `AQW_TELEMETRY=1` |

Jangan log per-tick tanpa throttle. Contoh throttle yang benar:
`CoreUltra._log_state_now` menulis hanya saat state berubah **dan** minimal
1×/5 detik. `_log_failed_skill` dibatasi 1 baris/2 detik.

---

## 11. Playbook porting: dari bot C# / Flash → script ini

Prasyarat: yang bisa di-port hanya bot yang bekerja di **level aksi server**
(join map, attack, quest, shop, party). Bot yang membaca/memodifikasi memori
Flash atau menggambar overlay tidak bisa di-port — engine ini bicara ke server
lewat socket, bukan ke client.

### Langkah

1. **Inventarisasi aksi.** Baca script sumber dan tulis daftar rata: setiap
   langkah + parameternya (nama map, cell/pad, id monster/quest, urutan skill,
   delay). Jangan langsung menulis kode.
2. **Kelompokkan.** Farm? Quest? Navigasi? Shop/bank? Party? Combat?
3. **Petakan** ke primitif di tabel bawah.
4. **Ganti loop & timer.** Loop bot lain → `while cmd.is_still_connected():` +
   `await cmd.sleep(ms)`. Jangan bawa pola "sleep lalu cek".
5. **Buang throttle skill sendiri.** Pacing ada di engine (`MIN_SKILL_GAP_MS`,
   `AUTO_ATTACK_MIN_GAP_MS`, `CD_START_DELAY_MS`). Menambah delay sendiri di
   sekitar cast = dobel-throttle dan bisa memicu warning "too soon".
6. **Set whitelist drop.** Tanpa itu, drop tidak diambil otomatis.
7. **Verifikasi** (§13).

### Tabel terjemahan aksi

| Aksi di bot lain (nama/paket umum) | Primitif di sini |
|---|---|
| enter / transfer map, `tfer` | `join_map(map, room)` |
| goto cell/pad, `moveToCell` | `jump_cell(cell, pad)` |
| walk to x,y, `mv` | `walk_to(x, y)` |
| follow player | `goto_player(name)` / `Bot(followPlayer=…)` |
| use skill / attack, `gar` | `use_skill(slot, target)` / `use_next_skill([...])` |
| attack until item/quest | `hunt_item(...)` / `kill_quest(...)` |
| use scroll/potion (slot 5) | `equip_scroll(name)` lalu `use_skill(5, target)` |
| auto-attack (slot 0) | `use_skill(0, target)` |
| target priority list | `target_monsters="id.1,id.2"` atau `monster_prio=` |
| accept quest, `acceptQuest` | `ensure_accept_quest(qid)` |
| complete/turn in, `tryQuestComplete` | `ensure_turn_in_quest(qid)` |
| is quest done / can turn in | `can_turnin_quest(qid)` |
| quest in progress | `quest_in_progress(qid)` |
| check item count | `is_in_inventory(name, qty)` / `get_quant_item(name)` |
| check bank | `is_in_bank(name)` |
| withdraw / deposit | `bank_to_inv(...)` / `inv_to_bank(...)` |
| buy / sell | `buy_item(shop, name, qty)` / `sell_item(name, qty)` |
| equip class/item | `equip_item(name)` |
| equip by enhancement/forge | `equip_enhancement(name, slot)` |
| drop whitelist / loot list | `Bot(itemsDropWhiteList=[...])` / `add_drop(...)` |
| wait N players | `wait_count_player(n)` |
| party invite / accept | packet `gp%1%pi` / `gp%1%pa` (§8) |
| dungeon queue | packet `dungeonQueue%25127%{map}%` (§8) |
| send chat | `send_chat(msg)` |
| fixed delay / throttle | `cmd.sleep(ms)` |
| custom/hardcoded packet | `send_packet(...)` / `bot.write_message(...)` |
| read packets / trigger on event | `subscribe(handler)` (§9) |
| respawn on death | otomatis (`handlers/death_handler.py`) — cukup cek `is_still_connected()` |
| relogin on disconnect/AFK | `Bot(autoRelogin=True)` |
| anti-staff / mod detection | `antiMod=True` (default) |
| goto label / jump index | **tidak ada** di script mode — tulis sebagai loop/fungsi |

### Yang **tidak** perlu di-port

GUI/window, animasi client, rendering, aimbot, pembacaan memori, kalkulasi
damage lokal yang tidak mempengaruhi keputusan, dan sistem config bot lama —
ganti dengan `config.py` bergaya `bot/ultra`.

### Kalau bot sumber punya "loadout/gear profile"

Petakan langsung ke pola §7: satu `Loadout` per (boss/slot/kelas), field kelas =
item name, sisanya nama enhancement.

---

## 12. Jebakan (pitfalls)

1. **`main` return = bot berhenti.** Loop terus atau akhiri dengan
   `await cmd.sleep(100000)`.
2. **Jangan `asyncio.sleep` di script** → `await cmd.sleep(ms)`. Pengecualian:
   di dalam task yang dibuat `create_task` (pola delayed taunt).
3. **Guard semua loop** dengan `cmd.is_still_connected()`, kalau tidak loop
   menggantung setelah disconnect.
4. **Jangan bikin delay skill sendiri.** Pacing = engine. Delay manual =
   warning "too soon".
5. **`add_drop` / `itemsDropWhiteList` wajib** atau drop tidak diambil.
6. **Predicate `@check_alive` mengembalikan `None`** saat disconnect
   (`is_monster_alive`, `get_monster_hp`, `hp_below_percentage`, dll.). `None`
   falsy, tapi jangan bandingkan dengan `False`; `get_monster_hp` memakai `-1`
   untuk "tidak ketemu".
7. **`equip_item` mengembalikan `False`** kalau item tak ada di inventory
   **maupun** bank. Tangani: kalau gear wajib, `stop_bot` (pola ultra).
8. **`normalize()`** melipat huruf kecil, spasi, backtick/quote. Cocokkan nama
   item seperti yang muncul di capture — apostrof sering beda karakter.
9. **`hunt_item` early-return** kalau qty sudah cukup, jadi aman dipanggil
   berulang; jangan bungkus dengan cek sendiri lalu lupa `add_drop`.
10. **Temp vs permanent inventory.** Quest item biasanya temp ⇒ `is_temp=True`.
11. **Satu proses = satu `Bot`.** Multi-akun = proses terpisah (templeshrine /
    `.bat`), bukan beberapa `Bot` dalam satu loop kecuali lewat GUI.
12. **`main` signature berarti**: parameter bernama `bot` ⇒ dikirim `Bot`.
    Selalu tulis `main(cmd: Command)`.
13. **Room privat** = `roomNumber` unik; `join_map(map)` tanpa room bisa masuk
    room publik dan merusak asumsi jumlah pemain.
14. **Party coordination harus gated** `party.enabled()` (atau cek env sendiri)
    supaya single-bot tetap jalan.
15. **`grimgaol.py` jangan disentuh** tanpa instruksi eksplisit (lihat
    `AGENTS.md`).
16. **`android/app/src/main/python/` adalah mirror manual.** Kalau Anda mengubah
    `core/`, mirror-kan atau katakan tidak di-mirror. (Menambah script di `bot/`
    juga perlu di-mirror kalau mau jalan di Android.)
17. **Jangan simpan kredensial di kode** kalau bisa dihindari — pola ultra
    memang menaruhnya di `config.py`, tapi minimal sadari itu (isu #4 di
    `knowledge.md` §14).

---

## 13. Checklist sebelum bilang selesai

```bash
python -m compileall -q core model bot templates tools commands abstracts handlers
python tools/test_imports.py        # semua entry point import & punya main/run
python tools/test_enhancement.py
python tools/test_skill.py
python tools/test_use_skill.py
python tools/test_equip_bank.py
python tools/test_equip_level.py
python tools/test_apply_loadout.py
python tools/check_loadouts.py      # semua nama gear/loadout resolve (exit 0)
```

Semua harus hijau. Kalau bot menyentuh gear/loadout, `check_loadouts.py` wajib
lulus. Kalau mengubah `core/`, jalankan juga suite capture (`tools/capture_run.py`
lalu `tools/check_transitions.py`) — jangan "menyederhanakan" konstanta pacing
tanpa itu.

Sebelum menyerahkan:

- [ ] Setiap loop punya `is_still_connected()`.
- [ ] Drop yang diharapkan sudah di whitelist / `add_drop`.
- [ ] Quest item pakai `is_temp=True`.
- [ ] Cast tanpa delay manual (pacing engine).
- [ ] Item/gear wajib: ditangani kalau `equip_item`/`equip_enhancement` `False`.
- [ ] `main(cmd: Command)`, `isScriptable=True`, `BOT_PATH` benar.
- [ ] Kalau multi-pane: koordinasi gated `party.enabled()`.

---

## 14. Di mana menaruh file & cara menjalankannya

| Isi | Lokasi |
|---|---|
| Satu item farm | `bot/<nama>.py` — contoh `bot/void_aura.py` |
| Sekumpulan item + wrapper | `bot/<tema>/core_<tema>.py` + `<item>.py` per item + `0_all_<tema>.py` — contoh `bot/darkon_mats/`, `bot/LR/` |
| Beberapa boss / banyak gear | `bot/<tema>/{config.py,core_*.py,<boss>.py}` — contoh `bot/ultra/` |
| Party master/slave | `bot/<tema>/<variant>/{bot_*.py,core/{config.py,core_*.py}}` — contoh `bot/templeshrine/` |

Menjalankan:

```bash
python start.py                      # pilih modul bot (bot.ultra.ultra_warden, dst.)
py -m bot.darkon_mats.a_melody       # via blok __main__ (input login)
py -m bot.ultra.daily                # runner multi-slot (pipe 1..4)
```

`BOT_PATH` di `.env`/`.bat` harus berisi module path yang mengekspos `main(cmd)`
(atau `main()` untuk `bot_temple.py` yang mengelola `asyncio.run` sendiri).

### Peta cepat file contoh per pola

| Pola | Baca ini |
|---|---|
| farm 1 item | `bot/darkon_mats/core_darkon_mats.py::a_melody` |
| banyak material + quest | `bot/LR/core_lr.py::revenant_spellscroll`, `::exalted_crown` |
| farm grup + kelas solo/farm | `bot/darkon_mats/core_darkon_mats.py::farm_mats` |
| boss + loadout + config | `bot/ultra/ultra_warden.py`, `bot/ultra/config.py` |
| `on_tick` finisher | `bot/ultra/ultra_warden.py::warden_tick` |
| state machine taunt | `bot/ultra/ultra_gramiel.py`, `bot/templeshrine/eclipse/core/core_eclipse.py` |
| party master/slave | `bot/templeshrine/temple/core/core_temple.py` |
| koordinasi lintas-proses | `bot/ultra/party.py` |
| logging per-akun | `bot/ultra/ultralog.py` |
| telemetry JSONL | `bot/ultra/telemetry.py` |

---

## 15. Peta konkret: bot sumber (C#) → engine ini

Sumbernya: `%APPDATA%\<nama-bot>\Scripts` (reference alias **`refscripts`**).

Di root folder itu ada API intinya — `CoreBots.cs`, `CoreFarms.cs`,
`CoreAdvanced.cs`, `CoreStory.cs`, `CoreDailies.cs`. **Script individu hampir
selalu cuma wrapper**: logika asli ada di `Core.*` dan `Bot.*`, jadi porting
biasanya berhenti di menerjemahkan panggilan itu.

Folder bot sumber yang sudah punya padanan di repo ini:

| Bot sumber | Python di sini |
|---|---|
| `Ultras-v3\Dependencies-Ultras\CoreEnginev3.cs`, `CoreUltrav3.cs` | `bot/ultra/core_ultra.py` |
| `Ultrasv3\IndividualUltras\*.cs` | `bot/ultra/ultra_*.py` |
| `Ultrasv3\Entwined Eclipse\*` | `bot/templeshrine/eclipse/` |
| `Darkon\*` | `bot/darkon_mats/` |
| `Legion\*` | `bot/LR/` |
| `Story\*` | `bot/story/`, `bot_cmds/story/` |

### `Core.*` (CoreBots) → `cmd.*`

| Bot sumber | Di sini |
|---|---|
| `Core.HuntMonster(map, monster, item, quant, isTemp=true)` | `await hunt_item(cmd, item_name=item, item_qty=quant, map_name=map, monster_name=monster, is_temp=isTemp)` |
| `Core.KillMonster(map, cell, pad, monster, item, quant, isTemp)` | `join_map` + `jump_cell(cell,pad)` + loop `use_next_skill` (atau `hunt_item` kalau ada `item`) |
| `Core.KillMonster(map, cell, pad, MonsterMapID, …)` | target `"id."+id` → `jump_to_monster("id.N")`, `use_skill(slot, "id.N")` |
| `Core.HuntMonsterQuest(questId, mapName, monsterName)` | `await kill_quest(cmd, quest_id, map_name, monster_name)` |
| `Core.HuntMonsterQuest(questId, log, (map,mon,class)[])` | loop: `ensure_accept_quest` → `hunt_item` per bahan → `ensure_turn_in_quest` |
| `Core.Join(map, cell="Enter", pad="Spawn", publicRoom)` | `await join_map(map, room)` lalu `await jump_cell(cell, pad)`. Room privat = angka unik; `publicRoom=true` ⇒ `join_map(map)` tanpa room |
| `Core.Jump(cell, pad)` | `await cmd.jump_cell(cell, pad)` |
| `Core.JumpWait()` | `await cmd.sleep(…)` (tunggu cell termuat) |
| `Core.EnsureAccept(qid)` | `await cmd.ensure_accept_quest(qid)` |
| `Core.EnsureComplete(qid, itemID=-1)` | `await cmd.ensure_turn_in_quest(qid, item_id)` |
| `Core.EnsureComplete(params int[])` | loop `ensure_turn_in_quest` |
| `Core.RegisterQuests(ids)` | `await cmd.register_quest(qid)` per qid (auto accept+turn-in di latar) |
| `Core.EnsureLoad(qid)` | tidak perlu — engine memuat data quest sendiri saat accept |
| `Core.CheckInventory(item, quant)` | `cmd.is_in_inventory(item, quant)` (**sync**); `toInv=true` ⇒ `await bank_to_inv(item)` dulu |
| `Core.CheckInventory(itemID, …)` | `cmd.bot.player.get_item_inventory_by_id(id)` |
| `Core.FarmingLogger(item, quant)` | `cmd.farming_logger(item, quant)` |
| `Core.AddDrop(items)` | `cmd.add_drop(items)` |
| `Core.GetMapItem(id, quant)` | `await cmd.get_map_item(id, qty)` |
| `Core.BuyItem(map, shopID, itemName, quant)` | `await cmd.buy_item(shop_id, name, qty)` |
| `Core.SellItem(itemName, quant)` | `await cmd.sell_item(name, qty)` |
| `Core.GetShopItems(map, shopID)` | `await cmd.load_shop(shop_id)` + `cmd.get_loaded_shop(shop_id)` |
| `Core.ToBank(items)` | `await cmd.inv_to_bank(items)` |
| `Core.Unbank(items)` | `await cmd.bank_to_inv(items)` |
| `Core.Equip(gear)` | `await cmd.equip_item(name)` |
| `Core.EquipClass(ClassType)` | `await cmd.equip_item(cmd.get_farm_class() or cmd.get_solo_class())` |
| `Core.AggroMonsters()` / `Core.ToggleAggro(b)` | `cmd.start_aggro(ids)` / `cmd.stop_aggro()` |
| `Core.IsMonsterAlive(name)` | `cmd.is_monster_alive(name)` |
| `Core.GetMonsterHP(monMapID)` | `cmd.get_monster_hp("id."+id)` |
| `Core.FindMonster(…)` | `await cmd.jump_to_monster(name)` |
| `Core.UsePotion()` | `await cmd.equip_scroll(name)` → `await cmd.use_skill(5, target)` |
| `Core.Message(msg, caption)` | `await cmd.send_chat(msg)` |
| `Core.Sleep(ms)` | `await cmd.sleep(ms)` |
| `Core.Rest()` | `await cmd.rest()` |
| `Core.SendPackets(…)` | `await cmd.send_packet(…)` |
| `Core.Relogin()` | `Bot(autoRelogin=True)` saat konstruksi |
| `Core.Logger(…)` | `print(…)` / `cmd.bot.debug(…)` |
| `Core.Shutdown<bot>()` | `cmd.stop_bot("…")` |
| `Core.SetOptions(…)` | tidak ada padanan — jadi argumen `Bot(...)` + `config.py` |

### `CoreAdvanced` → sini

| Bot sumber | Di sini |
|---|---|
| `Core.EnhanceItem(item, enh, …)`, `uValiance`, `uPenitence`, … | `await cmd.equip_enhancement("Valiance", slot)` |
| `Core.KillUltra(...)` | pola `bot/ultra` (`apply_loadout` → `attack_loop` → `finish`) |
| `Core.KillWithAura(...)` / `KillBossWithSecondary` | loop `use_skill` + cek `player.hasAura(name)` |
| `Core.EquipBestItemsForMeta` / `SmartEnhance` | tidak ada — gear ditulis eksplisit di `config.py` |

### `CoreFarms` / `CoreStory` / `CoreDailies`

| Bot sumber | Di sini |
|---|---|
| `Farm.Experience/Gold(…)`, `Farm.<Faction>REP(…)` | loop `hunt_item` di map yang sesuai; rep dibaca `player.getFactionRank(name)` |
| `Farm.FactionRep(...)`, `GetAllRanks()` | `cmd.get_player().FACTIONS` |
| `Story.QuestProgression` / `ChainQuest` / `KillQuest` | loop `ensure_accept_quest` → syarat → `ensure_turn_in_quest` |
| `Daily.<nama>()` | tulis langsung sebagai fungsi di `bot/<tema>/` |

### `Bot.*` (IScriptInterface) → `cmd` / `bot`

| Bot sumber | Di sini |
|---|---|
| `Bot.ShouldExit` | `not cmd.is_still_connected()` |
| `Bot.Player.Cell` / `.Pad` | `cmd.get_player().CELL` / `.PAD` |
| `Bot.Player.Health` / `.MaxHealth` / `.Mana` | `.CURRENT_HP` / `.MAX_HP` / `.MANA` |
| `Bot.Player.InCombat` | `.IS_IN_COMBAT` |
| `Bot.Player.Alive` | `not .ISDEAD` |
| `Bot.Player.HasAura(name)` | `.hasAura(name)` |
| `Bot.Inventory` / `Bot.Bank` / `Bot.TempInv` | `.INVENTORY` / `.BANK` / `.TEMPINVENTORY` |
| `Bot.Map.Name` | `cmd.bot.strMapName` |
| `Bot.Monsters` | `cmd.bot.monsters` |
| `Bot.Player.X` / `.Y` | `cmd.get_player_position_xy()` |
| `Bot.SendPacket(...)` | `await cmd.send_packet(...)` |
| `Bot.Events.*` | `cmd.subscribe(handler)` |
| `Bot.Sleep(ms)` | `await cmd.sleep(ms)` |

### Yang TIDAK punya padanan (jangan dipaksakan)

Tandai TODO / selesaikan lain: `EnsureCompleteChoose` (pilih reward quest),
`AbandonQuest` / `ResetQuest`, `CheckClassRank` / `RankUpClass`,
`EquipBestItemsForMeta` / `SmartEnhance`, `FindBestServer`,
`isSeasonalMapActive`, `AutoAddTags`, `Core.TrashCan` / `BankAC*`
(house/bank khusus), dan `Bot.Player.Level` (level tidak disimpan engine).

Sebaliknya, engine ini punya yang bot sumber tidak: `use_next_skill` (scheduler
readiness + pacing internal) dan koordinasi party lintas-proses
(`bot/ultra/party.py`).

### Aturan khusus saat porting dari bot sumber

- Bot sumber memakai `Bot.Sleep`/delay manual di dalam loop skill. Di sini **buang**
  delay itu; pakai `use_next_skill` atau `attack_loop`.
- `isTemp` bot sumber ⇒ `is_temp` di sini. Item quest = `true`.
- `Core.SetOptions()` mengurus kelas/drop/log secara global; di sini jadi
  argumen `Bot(...)`, `add_drop`, dan `config.py`.
- Bot sumber sering multi-akun (`Army/`, script `*Army*`). Padanannya pola party
  `bot/templeshrine` + `party.py` (proses terpisah), bukan satu proses.
- `IScriptInterface` sendiri **tidak ada** di folder `Scripts` (bagian app
  bot sumber). Kalau butuh definisi lengkapnya, tambahkan repo bot sumber di GitHub sebagai
  reference git.
- **Log lewat jalur log engine, bukan `print`**: `Core.Logger(...)` →
  `cmd.bot.log(...)` (terlihat; di balik `Bot.showLog`, bertimestamp seperti
  keluaran engine yang lain), dan yang sifatnya verbose → `cmd.bot.debug(...)`
  (di balik `showDebug`). Baris yang **ada di sumber** ditulis dengan teks
  sumber apa adanya, supaya log satu run bisa dibandingkan baris-per-baris
  dengan bot sumber; yang **tambahan kita** (mis. "engine ini tidak bisa X")
  diberi tag seperti `[vhl]` supaya bisa dibedakan di aliran yang sama.
  `tools/check_log_scope.py` mengaudit keduanya: `print` mentah, dan
  `cmd.bot.log` di fungsi yang tidak punya `cmd` (NameError yang menunggu run
  yang mencapainya).
- **Resolusi penerima dulu, jangan cocokkan nama**: kelas `Core*` di referensi
  **tidak saling mewarisi** (tidak ada `class CoreAdvanced : CoreBots`), jadi
  `Adv.BuyItem` dan `Core.BuyItem` adalah dua metode **berbeda** yang kebetulan
  senama — hanya versi CoreAdvanced yang menjalankan `GetItemReq` (rep, level,
  gold). Sebelum memetakan `X.Method` ke fungsi kita, tetapkan dulu kelas `X`-nya
  (`Adv.` → `bot/core_advanced.py`, `Core.` → `bot/core_bots.py`, `Farm.` →
  `bot/core_farms.py`, `Story.` → `bot/core_story.py`, `Daily.` →
  `bot/core_dailies.py`), lalu bandingkan badannya. Kalau nama itu muncul di lebih
  dari satu core, sebutkan kelas mana yang diikuti di docstring/komen kode kita.
  `tools/core_surface.py` memetakan kelas per berkas dan nama yang bertabrakan.
- **Python 3.12 minimum** (mesin ini: 3.12.10, `py -3.12`; 3.10 masih terpasang).
  Alasannya konkret: `bot/dragon_of_time/dragon_of_time.py` memakai backslash di
  dalam f-string, yang legal **sejak 3.12** saja. Jangan "perbaiki" berkas orang
  untuk menurunkannya — naikkan interpreter-nya. Dependensi yang harus ada di
  interpreter itu: `colorama` (engine: `Fore`), `requests` (login/HTTP),
  `bottle` + `Pillow` (GUI).

### Contoh tervalidasi: `Ultras/UltraWarden.cs` → `bot/ultra/ultra_warden.py`

Pilot pipeline. Sumber (v1, 156 baris); hasilnya: **setiap konstruksi punya
padanan**, dan port Python-nya sudah ada serta setara secara fungsi.

| bot sumber v1 | Python di sini |
|---|---|
| `Options` (DoEquipClasses, `a`/`b` taunter, DoEnh) | `bot/ultra/config.py` (`LOADOUTS`) |
| `Core.Boot()` | `bot.start_bot` + `CoreUltra.__init__` |
| `Prep()` → `Ultra.EquipClassSync(classes, 4, …)` | `apply_loadout(boss)` + slot di `daily.py` |
| `Ultra.GetScrollOfEnrage()` | `equip_scroll("Scroll of Enrage")` dari loadout |
| `C.EnsureAccept(8153)` | `await cmd.accept_quest(8153)` |
| `Core.Join(map)` | `join_and_wait("ultrawarden")` |
| `Ultra.WaitForArmy(3, …)` | `party.barrier(...)` + `wait_count_player(4)` |
| `Core.ChooseBestCell(boss)` | `BOSS_CELL="r2"` + `jump_cell("r2","Left")` |
| `Core.EnableSkills()` | tidak perlu — engine selalu mengirim skill |
| `while (!Bot.ShouldExit)` | `while cmd.is_still_connected()` |
| `if (!Bot.Player.Alive) Wait.ForTrue(…,20)` | `handlers/death_handler.py` + `@check_alive` |
| `Ultra.CheckArmyProgressBool(() => TempInv.Contains(…), sync)` | `fight_until_party_ready(quest, fight)` + `can_turnin_quest` |
| `Bot.Combat.Attack("*")` + `Bot.Sleep(250)` | `attack_loop([0,1,2,0,3,4], monster=…)` (pacing internal) |
| `C.EnsureComplete(8153)` | `turn_in_quest(8153)` (di dalam `fight_until_party_ready`) |
| `C.Jump("Enter","Spawn")` + `Adv.GearStore` | `finish(quest)` → Enter → `yulgar` → `rest()` |

Boleh berbeda (ini cuma *logic bertarung*, tidak perlu 1:1):

- **Taunt** — v1: HP-band 5% + spam potion sampai aura `Focus`; v3: pulse 5 detik
  + 60× `Cast(5)`. Python: tanpa taunt, diganti `monster_prio` + `heal_below`.
- **Cell** — bot sumber `ChooseBestCell(boss)` vs Python hardcode `r2`/`Left`.
- **Finisher 600k** — tidak ada di v1 maupun v3; tambahan lokal Python.
- **Drop** — bot sumber `AddDrop("Warden Insignia")`; Python tidak (item quest tetap
  masuk via `addItems` → temp inventory).

Kemampuan yang bot sumber punya tapi `CoreUltra` sini belum — penting kalau port boss
baru yang belum ada padanannya:

1. **Potion/alchemy** — `UseAlchemyPotions(tonic, elixir)`,
   `ActivateEquippedPotion()`. Sebagian sudah ada (`cmd.use_potion`,
   `equip_scroll` + `use_skill(5)`); pemilihan tonic/elixir terbaik belum.
2. **Taunt loop terjadwal** — `UltraAsync.StartTauntLoop` (pulse 5 dtk, 2 taunter
   bergantian, tiap giliran 60× cast slot 5). Belum ada padanan.
3. **`ChooseBestCell(boss)`** — sudah ada padanannya, `cmd.choose_best_cell()`
   (dan `jump_to_monster`, yang sekalian lompat).

### Porting Core bot sumber: sebaran yang bisa dan tidak

`CoreBots.cs` saja 469 KB / 157 method, tapi sebagian besar tidak relevan di
sini. Dibagi tiga ember:

**A. Portabel dan sudah di-port** (ada di `core/` sekarang):

| Bot sumber | Di sini |
|---|---|
| `CoreFarms.FactionRank` / `FactionRep` | `cmd.get_faction_rank()` / `cmd.get_faction_rep()` |
| `CoreFarms.RemainingFactionRepToMax` | `cmd.get_faction_remaining_to_max()` |
| `CoreFarms.MaxFactionRep` + `RepThresholds` | `model/faction.py`: `MAX_REP`, `RANK_THRESHOLDS` |
| `CoreFarms.TotalFactionRep` | `Faction.total_rep()` — **rumus bot sumber tidak disalin**, lihat docstring-nya |
| `CoreAdvanced.ChooseBestCell` | `cmd.choose_best_cell(monster)` |
| `Core.CancelRegisteredQuests` | `cmd.unregister_quest(qid)` / `cmd.cancel_registered_quests()` |
| `Core.UsePotion` | `cmd.use_potion(potion_id)` |
| `Bot.Player.Level` | `player.LEVEL` (dibaca dari `initUserDatas`) |
| data quest (`getQuests`) | `model/quest.py` → `Quest` (`slot`/`value`, `is_once`/`field`, `turn_in_items`, `reward_names`); dibaca lewat `cmd.get_loaded_quest(qid)` |

**B. Portabel tapi isinya data/konten** — kerjakan hanya kalau ada script yang
butuh: tabel per-faction (`faction → map, cell, pad, monster, quest ids`) untuk
~60 faction + `farm_faction_rep(...)`; `CoreFarms.Gold` / `Experience` beserta
metodenya (HonorHall, BattleGroundE, BerserkerBunny, IcestormArena);
`CoreDailies` (35 routine); `CoreStory` (`KillQuest` / `MapItemQuest` /
`BuyQuest` / `ChainQuest`); `GetBoost` (quest 1614/1615).

**C. TIDAK portabel** — butuh panggilan client-side Flash atau state internal
bot sumber yang tidak lewat socket:

- `Bot.Quests.IsUnlocked` / `Tree` + `Bot.Flash.CallGameFunction("world.getQuestValue", slot)` —
  inti `CoreStory.QuestProgression`. Yang **sudah** tersedia: `iSlot`/`iValue`
  (posisi chain) lewat `Quest.slot`/`.value`, dan `bOnce`/`sField` lewat
  `Quest.needs_single_turn_in`. Yang tetap tidak ada: nilai slot *berjalan* dan
  status unlocked. Versi di sini memakai `is_completed_before` + `can_turnin_quest`.
- `Bot.Wait.ForPickup` / `ForTrue` / `ForCellChange` / `ForMapLoad` → ganti loop
  `while` + `cmd.sleep`.
- `Core.SavedState` / `CheckSaveState` / `ExecuteSaveState` (state recovery).
- `Core.TrashCan` (hapus item dari inventory).
- `SmartEnhance` / `EquipBestItemsForMeta` (butuh data gear meta).
- Options system, CBO config, compiled-script manager, `FindBestServer`,
  `isSeasonalMapActive`, `AutoAddTags`.

**Substitusi yang sudah terbukti cukup** (dari audit `Nation/Materials`, 15 file):

| Bot sumber | Cara di sini |
|---|---|
| `Core.JoinSWF(map, swf, cell, pad)` | `join_map(map)` + `jump_cell(cell, pad)` — SWF cuma aset render client |
| `Core.QuestRewards(id)` | `cmd.get_quest_rewards(id)` / `cmd.add_quest_rewards(id)` — nama reward datang dari payload `getQuests` di `oRewards` (bentuknya tidak seragam, lihat catatan di bawah) |
| `Core.CBOBool(key, out bool)` | parameter fungsi |
| `Bot.Options.*` (`CanWeAggro`, `AttackWithoutTarget`) | paket aggro (`start_aggro`/`stop_aggro`); targeting kita eksplisit |
| `Core.EnsureCompleteMulti(id, amount, item)` | `ensure_turn_in_quest(id, item, amount)` — bot sumber memakai `world.maximumQuestTurnIns` untuk batas atas; kita loop sampai quest lepas dari in-progress |
| `Core.EnsureCompleteChoose(id[, item])` | `turn_in_quest(id, item_id)` — "choose" tidak lain parameter `itemID` |
| `Bot.Wait.For*` | loop `while` + `cmd.sleep` |
| `Core.ResetQuest` | `ensure_accept_quest(qid)` — **tidak perlu API baru.** Di wire `ResetQuest` hanya `getQuests` + `acceptQuest` (×3); `AbandonQuest` tidak mengirim packet apa pun (murni state lokal Flash), jadi tidak ada yang bisa di-sniff. |

### Reward quest: bentuk payload-nya tidak seragam

Ini jebakan yang sudah memakan waktu sekali — dicatat supaya tidak terulang.
Payload `getQuests` **tidak menyeragamkan** bentuk reward:

| Bentuk | Contoh |
|---|---|
| bersarang | `"oRewards": {"itemsC": {"0": {...}}}` |
| datar | `"oRewards": {"0": {...}}` |
| array | `"oRewards": [{...}]` |
| tanpa nama | `oRewards` ada, tapi entrinya tidak punya `sName` |
| tanpa reward | `oRewards` tidak ada sama sekali |

Di sebelahnya selalu ada `reward`: array ringan `{ItemID, iQty, iType, iRate}`
(`iType == 2` = choice reward). Itu yang membedakan *"tidak punya reward"* dari
*"punya reward tapi namanya tidak dikirim"*.

`model/quest.py` **menelusuri** `oRewards` alih-alih meng-index satu kunci, jadi
tiga bentuk pertama terbaca sama:

```python
cmd.get_quest_reward_entries(quest_id)   # [(item_id, name, max_stack), ...]
cmd.get_quest_rewards(quest_id)          # [name, ...]
```

Keluaran kosong berarti salah satu dari dua hal, dan `Quest.reward_ids` yang
membedakannya. Kalau `reward_ids` berisi tapi nama kosong, **tidak ada cara**
mendapatkan nama itu dari payload — si pemanggil harus menyebut nama itemnya.
Itulah sebabnya routine seperti `new_worlds_new_opportunities` menerima `item`
sebagai argumen, dan kenapa kembalinya daftar kosong tanpa pesan itu bahaya:
di engine ini `main()` yang selesai = bot berhenti, jadi "tidak ada yang
di-farm" terlihat persis seperti "selesai".

## 16. Register cacat bot sumber (deviasi port)

Aturan kerjanya: **ikut sumbernya apa adanya; deviasi hanya kalau cacatnya masuk
kelas (i)/(ii) di bawah DAN pemilik repo sudah memutuskannya.** Jangan
menyimpulkan nilai yang sumbernya tidak tulis (nama item, cell, nama reward) —
pakai literal sumbernya, walau kelihatannya salah. Tiap deviasi yang disetujui
dapat tiga hal: catatan satu baris di berkasnya, tes offline yang mengunci
perilaku port, dan satu baris di tabel bawah ini. Tabelnya untuk audit: kalau
sumbernya berganti versi, tiap baris bisa dicek ulang (grep nama metode di kolom
1, baca ulang, putuskan baris itu masih berlaku).

Klasifikasi cacatnya, dan wajib-tidaknya deviasi:

| Jenis | Akibat kalau ditiru | Sikap |
|---|---|---|
| (i) farming selamanya | bot menggantung tanpa pesan | **wajib deviasi** |
| (ii) diam-diam tidak melakukan apa pun | bot berhenti, terlihat "selesai" | **wajib deviasi** |
| (iii) mati / kosong | tidak ada | cukup dicatat |

| Sumber | Cacat | Perilaku port | Verifikasi live | Tes |
|---|---|---|---|---|
| `CoreNation.ApprovalAndFavor` | `!ShouldExit && a < q \|\| f < q` — `&&` lebih kuat, jadi tetap loop setelah ShouldExit | berhenti saat disconnect | — | `approval : partial …` |
| `CoreNation.BambloozevsDrudgen(null)` | `CheckInventory(null, quant)` tak pernah benar → (i) | `item=None` ditolak + dilaporkan | — | `bamboozle : no item …` |
| `CoreNation.CragName` | literal berisi HTML escape `Crag &amp; Bamboozle`, jadi 20 cek pet Crag-nya tak pernah cocok | escape-nya **sudah diperbaiki** jadi `Crag & Bamboozle` (commit `fb46fe5`) → rute pet hidup; `CRAG_PET` memakai nama polos | — | — |
| `CoreNation.Forge*` (4 dari 5 guard) | guard `!gemstone && !member` — longgar dari pesannya sendiri | **diikuti C#**; loop melaporkan penolakan server, bukan spin | accept 4920/4921 tanpa Gemstone → pesan penolakan | `forge dcs : loose guard …` |
| `CoreNation.ForgeTaintedGems` | guard `\|\|` (yang ketat) — satu-satunya yang konsisten | diikuti | — | `forge : strict guard …` |
| `CoreNation.ForgeDarkCrystalShards` | cek `"Dark Crystal Shards"` (plural) → stop condition tak pernah benar → (i) | **diikuti sumber**: loop jalan sampai bot dihentikan | — | `forge dcs : the literal … ends the farm` |
| `CoreNation.ForgeDiamondsOfNulgath` | cek `"Diamonds for Nulgath"` — nama itu tak ada itemnya | **diikuti sumber** | — | `forge dia : the literal …` |
| `CoreNation.CarveUniGemStone(null)` | loop sampai bot dihentikan | "All" = sampai kelima reward penuh | — | `carve : a named reward …` |
| `CoreNation.SwindlesBilk` | isinya hanya `AddDrop`, tanpa aksi | tidak diport | — | — |
| `CoreFarms.IcestormArena` | pita 35-50: jalur hidup `r11` (cell pita 30-35), jalur mati `r14` | **diikuti sumber** (`r11`) | — | belum |
| `CoreFarms.ToggleBoost` / `GetBoost` | butuh boost item (fitur klien sumber); default-nya semua off | dihapus; ada komentar di tiap titik yang di sumber memanggilnya | — | — |
| `CoreFarms.Experience(rankUpClass: true)` | butuh rank class | dilaporkan tak didukung, lanjut ke target level | — | belum |
| `Nation/Various/HanzoOrbQuest.cs` | reward default `"Any"` bukan nama reward → (i) | nama tak dikenal → lapor + daftar reward asli | — | `carve`-style, `hanzo …` |
| `Nation/Various/VoidDestroyer.cs`, `VoidSpartan.cs`, `JuggernautItems.cs` | guard `toInv: false` (hanya inventory) padahal itemnya **dibank** di akhir → run berikutnya farming ulang | cek bank-aware (sesuai permintaan) | — | jalan wrapper |
| `Nation/Various/TendurrrTheAssistantQuests.cs` | opsi reward berisi *indeks* (0-3) tapi dicari sebagai item id; cabang All kehilangan `!`; membaca reward list quest 837 | pakai payload quest 5814 + cek bank-aware | — | jalan wrapper |
| `Nation/Various/CarveTheUnidentifiedGemStone[Member].cs` | enum hanya 4 dari 5 reward; `ToString()` memberi `Dark_Crystal_Shard` yang bukan nama item → (i) | daftar lima nama; `REWARD = None` = semua | — | `carve : unknown reward …` |
| `Nation/NulgathsCombatStyles/SoulReaperofNulgath.cs` | template kosong (`//INSERT CODE HERE`) | tidak diport | — | — |
| `CoreBots.EnsureAccept` (`BlackKnightOrb`, `VHLChallenge`) | tak punya jalur gagal: `Bot.Quests.EnsureAccept` + `Wait.ForQuestAccept` tanpa batas, kembaliannya selalu `true` | `ensure_accept_quest` dibatasi + lapor; pemanggil berhenti daripada berburu untuk quest yang tak aktif | — | `blackknight : quest 318 refused …`, `vhl : quest 5660 refused …` |
| `CoreAdvanced.RankUpClass` (lewat `CoreVHL.GetVHL`) | butuh rank class, yang engine ini tak bisa baca | dilaporkan, dilewati; kelasnya sendiri tetap didapat | — | `vhl : the class is already held …` |
| `CoreDailies.CheckDailyv2` / `DailyRoutine` (lewat `EldersBlood`) | gate harian dari flag klien `Bot.Quests.IsDailyComplete`; engine tak menyimpannya | gate = penolakan server saat accept; ditolak → lapor, tidak bertani | — | `elders : a refused accept …` |
| `Bot.Wait.ForPickup` (`BlackKnightOrb`, `EldersBlood`, `VHLChallenge`) | tunggu tanpa batas sampai drop masuk | `wait_for_item`: poll terbatas + lapor kalau tak datang | — | `pickup : held is immediate …` |
| `CoreVHL.FarmExtra` | nama reward 57446 dibaca dari cache quest klien, sebelum quest di-accept | quest di-accept dulu (`swindle_return` juga begitu) lalu dibaca dari payload; tetap tak ada → lapor | — | `vhl : reward 57446 …` |
| `CoreFarms.BlacksmithingREP` | cabang gold memanggil `Core.BuyItem` **dua kali** berturut-turut: sekali di `else` cek "sudah punya voucher", lalu sekali lagi tanpa syarat → saat stok kurang, voucher dibayar dobel | **diikuti sumber** (tidak "diperbaiki"); `RemainingFactionXp` diturunkan dari rep + tabel kita, sebab sumber membacanya dari daftar rep klien | — | gerbang; tes khusus menyusul |
| `Bot.Quests.IsUnlocked(q)` (dipakai `UnlockForgeEnhancements`) | cek nilai slot quest sisi klien: `q.Slot < 0 \|\| world.getQuestValue(q.Slot) >= q.Value - 1` — engine ini tidak punya klien untuk ditanya | untuk quest **one-time** (`bOnce`/`sField`) diganti `is_completed_before(q)` dan rantainya dikerjakan **berurutan**, jadi saat giliran tiba prasyaratnya baru selesai dan quest itu memang terbuka; quest yang tetap ditolak dilaporkan `ensure_accept_quest`. Mekanisme beda, hasil setara untuk rantai linier | — | `lacerate`, `forge_weapon` (import + gerbang) |
| `CoreStory.QuestProgression` | bukan sekadar cek: loop pemulihan — selesaikan ulang quest sebelumnya bila itemnya ada, relog setelah 5 gagal | **tidak diport**; port kita memakai `is_completed_before` sebagai gerbang lalu mengerjakan langkahnya. Pemulihan otomatisnya hilang | — | — |
| `CoreFarmerJoe.Pets` | parameternya diabaikan; badannya membaca key config `"Pets"` yang bukan opsi yang ia deklarasikan (`"PetChoice"`), jadi nilainya selalu default `None` → **metodenya mati**: dua panggilan `Pets(HotMama)`/`Pets(Akriloth)` dari `DoAll` tak pernah berbuat apa-apa | **(iii) diikuti sumber**: parameter diterima tapi tidak dipakai, `PET_CHOICE` = `PET_NONE`; mengubah konstanta itu menghidupkan cabangnya, sama seperti menyetel opsi di sumber | — | `pets : the parameter is ignored, as the source ignores it …` |

Empat titik yang **selera, bukan bug** — sudah diputuskan pemilik repo:

| Titik | Pilihan | Alternatif |
|---|---|---|
| `bamboozle_vs_drudge(item=None)` | tolak + lapor | tiru C# (loop selamanya) |
| `carve_uni_gem_stone(item=None)` | "All" = sampai penuh | C# = loop sampai dihentikan |
| guard `toInv: false` | cek bank-aware | C# = hanya inventory, lalu dibank |
| guard Forge `&&` | **ikut C#** (longgar) + loop melaporkan penolakan | wajibkan keduanya |
| nama item Forge, cell arena, nama Crag | **ikut literal sumber** (ejaan "salah" sekalipun) | pakai ejaan yang menurut kita "seharusnya" |
