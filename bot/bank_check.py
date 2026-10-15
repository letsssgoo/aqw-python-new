"""Report how the engine sees an item: bank first, then inventory.

Diagnostic for "the item is in my bank, but the script keeps farming it".  Run
it as a script (``BOT_PATH=bot.bank_check``, no arguments) and read the report:
for each name below it prints what the bank holds, what the inventory holds,
and what the bank-aware check decides -- pulling the stock across when the bank
has it, exactly as a farm guard does.

Reading the output:

* ``bank 0 (matched=False)`` -- the bank does not hold that name.  Either it is
  banked under a different spelling, or ``loadBank`` came back empty (it retries
  three times and prints when it gives up).
* ``inventory 40 -> 340`` -- the withdrawal happened, and ``has_item`` then
  answers from the inventory.

Warning: the check moves banked stock into the inventory, on purpose -- that is
the behaviour under test.  The sample and the "contains" lines come first, so
the bank's own view is printed before anything moves.
"""
from colorama import Fore

from core.command import Command

#: Names to inspect: add the ones you expect to be sitting in the bank.
ITEMS = [
    "Nulgath Larvae",
    "Unidentified 10",
    "Unidentified 13",
    "Nulgath's Approval",
    "Archfiend's Favor",
    "Drudgen the Assistant",
    "Tendurrr The Assistant",
]

#: Substrings to scan the bank for, so a spelling difference still shows up.
NEEDLES = ["nulgath", "unidentified", "larvae"]


async def main(cmd: Command):
    player = cmd.bot.player
    print(Fore.CYAN + f"[bank] {len(player.BANK)} items in the bank, "
          f"{len(player.INVENTORY)} in the inventory." + Fore.RESET)

    for entry in player.BANK[:10]:
        print(f"[bank]   sample: id={entry.item_id} "
              f"name={entry.s_name!r} qty={entry.qty}")

    for needle in NEEDLES:
        found = [e.s_name for e in player.BANK if needle in e.item_name]
        print(f"[bank] bank entries containing {needle!r}: {found[:12]}")

    for name in ITEMS:
        in_bank, bank_qty = player.isInBank(name)
        before = cmd.get_quant_item(name)
        owned = await cmd.has_item(name)
        after = cmd.get_quant_item(name)
        print(f"[bank] {name!r}: bank {bank_qty} (matched={in_bank}) | "
              f"inventory {before} -> {after} | has_item={owned}")
