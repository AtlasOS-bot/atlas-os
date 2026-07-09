from dataclasses import dataclass


@dataclass
class MarketResult:
    provider: str
    average_price: float | None
    lowest_price: float | None
    highest_price: float | None
    sold_count: int | None
    last_sale_price: float | None = None
    last_sale_date: str | None = None
    confidence: str = "UNKNOWN"
    notes: str = ""