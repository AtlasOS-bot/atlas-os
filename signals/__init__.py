from signals.collaboration import (
    CollaborationSignal,
)
from signals.collector_interest import (
    CollectorInterestSignal,
)
from signals.collector_value import (
    CollectorValueSignal,
)
from signals.exclusive import (
    ExclusiveSignal,
)
from signals.historical_pattern import (
    HistoricalPatternSignal,
)
from signals.limited_release import (
    LimitedReleaseSignal,
)
from signals.official_source import (
    OfficialSourceSignal,
)
from signals.reprint import (
    ReprintSignal,
)
from signals.restock import (
    RestockSignal,
)
from signals.shock_drop import (
    ShockDropSignal,
)


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
    CollectorValueSignal(),
]