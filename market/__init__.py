from market.manual import ManualMarketProvider
from market.ebay import EbayProvider
from market.stockx import StockXProvider
from market.tcgplayer import TCGPlayerProvider
from market.pricecharting import PriceChartingProvider


ALL_MARKET_PROVIDERS = [
    ManualMarketProvider(),
    EbayProvider(),
    StockXProvider(),
    TCGPlayerProvider(),
    PriceChartingProvider(),
]