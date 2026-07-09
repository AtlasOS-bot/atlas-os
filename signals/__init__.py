from signals.official_source import OfficialSourceSignal
from signals.limited_release import LimitedReleaseSignal
from signals.exclusive import ExclusiveSignal
from signals.collaboration import CollaborationSignal
from signals.shock_drop import ShockDropSignal
from signals.restock import RestockSignal
from signals.reprint import ReprintSignal
from signals.historical_pattern import HistoricalPatternSignal
from signals.collector_interest import CollectorInterestSignal


ALL_SIGNALS = [
    OfficialSourceSignal(),
    LimitedReleaseSignal(),
    ExclusiveSignal(),
    CollaborationSignal(),
    ShockDropSignal(),
    RestockSignal(),
    ReprintSignal(),
    HistoricalPatternSignal(),
    CollectorInterestSignal(),
]