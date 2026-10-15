"""Farm the Assisting Crag & Bamboozle daily rewards (quest 5817).

Port of ``Nation/AssistingCragAndBamboozle[Mem].cs``.  Members only, needs the
Crag & Bamboozle pet, and needs Sparrow's Blood in hand: the daily that supplies
it is CoreDailies work that is not ported, so the routine says so rather than
farming against a quest it cannot feed.

Choose one (by item id, which is how the quest picks):
  * ``None``  -- everything not maxed (the C# Get_whats_not_maxed option)
  * ``4670``  Sword of Nulgath
  * ``4769``  Tainted Gem
  * ``4770``  Dark Crystal Shard
  * ``4771``  Diamond of Nulgath
  * ``4752``  Unidentified 19
  * ``5357``  Totem of Nulgath
  * ``5586``  Elders' Blood
  * ``6136``  Gem of Nulgath
  * ``22332`` Blood Gem of the Archfiend
  * ``4861``  Voucher of Nulgath
  * ``4862``  Voucher of Nulgath (non-mem)
"""
from core.command import Command
from bot.nation.core_nation import assisting_crag_and_bamboozle

#: Change to one of the above.
REWARD_ID = None


async def main(cmd: Command):
    await assisting_crag_and_bamboozle(cmd, REWARD_ID)
