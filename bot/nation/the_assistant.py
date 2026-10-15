"""Farm quest 2859 (The Assistant) rewards, spending gold on War-Torn Memorabilia.

Port of ``Nation/TheAssistant.cs``.  The C# script has a reward picker and a
``farmGold`` toggle; both are set below.

``ITEM`` -- one of quest 2859's rewards, or ``None`` for all of them.  The
    exact names only exist once the quest is accepted (the payload decides), so
    a typo is reported as "not one of quest 2859's rewards".  ``None`` is always safe.
``REWARD`` -- quest 7551 reward to take each pass, or ``None``:
  * ``None``                          -- skip the Swindle's Return step
  * ``"Tainted Gem"``
  * ``"Dark Crystal Shard"``
  * ``"Diamond of Nulgath"``
  * ``"Gem of Nulgath"``
  * ``"Blood Gem of the Archfiend"``
"""
from core.command import Command
from bot.nation.core_nation import the_assistant

#: Change per the list above.
ITEM = None
QUANT = 1000
FARM_GOLD = True
REWARD = None
RETURN_POLICY = False


async def main(cmd: Command):
    await the_assistant(cmd, ITEM, QUANT, FARM_GOLD, REWARD, RETURN_POLICY)
