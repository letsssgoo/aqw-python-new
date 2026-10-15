# {
#     'FactionID': '46',
#     'CharFactionID': '45578506',
#     'sName': 'Aegis',
#     'iRep': '302500'
#   }
from core.utils import normalize

#: Reputation at rank 10 -- the cap every faction shares.
MAX_REP = 302500

#: ``(rank, cumulative rep required)``, highest first. The same numbers the reference bot's
#: ``CoreFarms.RepThresholds`` uses, so a rank read here matches the reference bot's.
RANK_THRESHOLDS = (
    (10, 302500),
    (9, 202500),
    (8, 129600),
    (7, 78400),
    (6, 44100),
    (5, 22500),
    (4, 10000),
    (3, 3600),
    (2, 900),
    (1, 0),
)


class Faction:
    def __init__(self, faction: dict):
        self.faction_id: int = int(faction.get('FactionID', 0))
        self.char_faction_id: str = str(faction.get('CharFactionID', ''))
        self.faction_name: str = normalize(faction.get('sName', ''))
        self.rep: int = int(faction.get('iRep', 0))
    
    def get_rep(self) -> int:
        return self.rep
    
    def add_rep(self, irep: int) -> None:
        self.rep += irep
    
    def is_max(self) -> bool:
        return self.get_rank() == 10

    def remaining_to_max(self) -> int:
        """Reputation still needed to reach rank 10 (0 once maxed).

        The counterpart of the reference bot's ``CoreFarms.RemainingFactionRepToMax``,
        recomputed from :data:`MAX_REP` instead of trusting a client-side
        ``RemainingRep`` field this engine never receives.
        """
        return max(0, MAX_REP - self.rep)

    def total_rep(self) -> int:
        """Reputation accumulated so far.

        ``rep`` is already cumulative here: the server reports only the rep
        *gained* (``addGoldExp.iRep``) and :meth:`Player.addRepToFaction` adds
        it up.  the reference bot's ``TotalFactionRep`` adds the rank threshold back on
        because its model stores within-rank rep -- do not copy that here.
        """
        return self.rep

    def get_rank(self) -> int:
        for rank, required in RANK_THRESHOLDS:
            if self.rep >= required:
                return rank
        return 1