"""
Deterministic, explainable text extraction primitives for Module 2.

No network calls, no external AI/embeddings - only regular
expressions, keyword dictionaries, phrase matching, proximity rules,
and simple arithmetic. Every function here either returns a plain
value or a small dict describing exactly what text produced it, so a
caller can always explain a detection.
"""

import re


# ---------------------------------------------------------------
# Negation handling
# ---------------------------------------------------------------

NEGATION_TRIGGER_WORDS = {
    "not",
    "no",
    "never",
    "without",
    "isn't",
    "wasn't",
    "aren't",
    "weren't",
    "don't",
    "doesn't",
    "didn't",
    "none",
}


def _words_before(text, position, count):
    prefix = text[:position]
    tokens = re.findall(r"[A-Za-z']+", prefix)
    return [token.lower() for token in tokens[-count:]]


def is_locally_negated(text, position, window=4):
    """
    True if one of the `window` words immediately before `position`
    is a negation trigger ("not exclusive", "no purchase required",
    "not limited", "no membership required", "not sold out", "no
    resale value", "not a collaboration").
    """
    return any(
        word in NEGATION_TRIGGER_WORDS
        for word in _words_before(
            text, position, window
        )
    )


UNLIMITED_PATTERN = re.compile(
    r"\bunlimited\s+(?:stock|quantity|supply|"
    r"units|availability)\b",
    re.IGNORECASE,
)


def has_unlimited_override(text):
    """
    "unlimited stock" negates limited-quantity language without a
    "not"/"no" trigger word immediately before it.
    """
    return bool(UNLIMITED_PATTERN.search(text))


# ---------------------------------------------------------------
# Confirmed / estimated / rumored classification
# ---------------------------------------------------------------

ESTIMATE_MARKERS = [
    "approximately",
    "expected",
    "projected",
    "reportedly",
    "believed to be",
    "around",
    "estimated",
    "roughly",
    "close to",
]

RUMOR_MARKERS = [
    "rumor",
    "rumored",
    "leak",
    "leaked",
    "unconfirmed",
    "allegedly",
    "possibly",
    "may release",
    "might release",
    "supposedly",
]


def classify_certainty(text, position, window=70):
    """
    Looks at a window of characters around `position` and returns
    "rumored", "estimated", or "confirmed". Rumor language always
    wins over estimate language when both are nearby - a rumor must
    never be treated as confirmed.
    """
    local = text[
        max(0, position - window):
        position + window
    ].lower()

    if any(
        marker in local for marker in RUMOR_MARKERS
    ):
        return "rumored"

    if any(
        marker in local
        for marker in ESTIMATE_MARKERS
    ):
        return "estimated"

    return "confirmed"


def certainty_flags(certainty):
    return {
        "confirmed": certainty == "confirmed",
        "estimated": certainty == "estimated",
        "rumored": certainty == "rumored",
    }


# ---------------------------------------------------------------
# Currency / price extraction
# ---------------------------------------------------------------

_AMOUNT = r"([\d][\d,]*(?:\.\d{1,2})?)"

CURRENCY_PATTERNS = [
    (re.compile(r"\$\s?" + _AMOUNT), "USD"),
    (
        re.compile(
            r"USD\s?" + _AMOUNT, re.IGNORECASE
        ),
        "USD",
    ),
    (
        re.compile(
            _AMOUNT + r"\s?USD", re.IGNORECASE
        ),
        "USD",
    ),
    (re.compile(r"€\s?" + _AMOUNT), "EUR"),
    (
        re.compile(
            _AMOUNT + r"\s?(?:EUR|euros?)",
            re.IGNORECASE,
        ),
        "EUR",
    ),
    (re.compile(r"£\s?" + _AMOUNT), "GBP"),
    (
        re.compile(
            _AMOUNT + r"\s?(?:GBP|pounds?)",
            re.IGNORECASE,
        ),
        "GBP",
    ),
    (
        re.compile(r"¥\s?" + r"([\d][\d,]*)"),
        "JPY",
    ),
    (
        re.compile(
            r"([\d][\d,]*)\s?(?:JPY|yen)",
            re.IGNORECASE,
        ),
        "JPY",
    ),
]


def find_currency_amounts(text):
    """
    Returns every currency mention found, sorted by position, as
    dicts: {start, end, amount, currency, matched_text}.
    """
    results = []

    for pattern, currency in CURRENCY_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1).replace(",", "")

            try:
                amount = float(raw)
            except ValueError:
                continue

            results.append({
                "start": match.start(),
                "end": match.end(),
                "amount": amount,
                "currency": currency,
                "matched_text": match.group(0),
            })

    results.sort(key=lambda item: item["start"])

    # A single number can be matched by more than one pattern
    # (e.g. "$200" matching both the $ pattern and, if it also
    # happened to say "200 USD" elsewhere, a second pattern) - dedup
    # overlapping spans, keeping the first (most specific) match.
    deduped = []

    for item in results:
        if any(
            item["start"] < existing["end"]
            and item["end"] > existing["start"]
            for existing in deduped
        ):
            continue

        deduped.append(item)

    return deduped


SPEND_CONTEXT_WORDS = [
    "spend",
    "spent",
    "spending",
    "required to spend",
    "purchase",
    "purchases",
    "eligible",
]

RESALE_CONTEXT_WORDS = [
    "resale",
    "resold",
    "reselling",
    "secondary market",
    "selling for",
    "sold for",
    "going for",
    "sell for",
    "sets are selling",
]

RETAIL_CONTEXT_WORDS = [
    "retail",
    "msrp",
    "price is",
    "priced at",
    "costs",
    "cost is",
    "sticker price",
]


def _context_window(text, start, end, radius=45):
    return text[
        max(0, start - radius): end + radius
    ].lower()


def classify_price_context(text, start, end):
    """
    Decides whether a currency amount most likely represents a
    required spend, an observed/estimated resale price, a plain
    retail price, or is unclassified, based on nearby words.
    """
    window = _context_window(text, start, end)

    if any(
        word in window
        for word in RESALE_CONTEXT_WORDS
    ):
        return "resale"

    if any(
        word in window for word in SPEND_CONTEXT_WORDS
    ):
        return "spend"

    if any(
        word in window
        for word in RETAIL_CONTEXT_WORDS
    ):
        return "retail"

    return None


COMPLETE_SET_MARKERS = [
    "complete set",
    "complete promo set",
    "full set",
    "entire set",
    "whole set",
]


def mentions_complete_set(text, start, end):
    window = _context_window(
        text, start, end, radius=60
    )

    return any(
        marker in window
        for marker in COMPLETE_SET_MARKERS
    )


# ---------------------------------------------------------------
# Quantity extraction
# ---------------------------------------------------------------

WORD_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def word_to_number(word):
    word = word.lower().strip()

    if word.isdigit():
        return int(word)

    return WORD_NUMBERS.get(word)


LIMITED_QUANTITY_PATTERNS = [
    re.compile(
        r"limited to\s+([\d,]+|"
        + "|".join(WORD_NUMBERS)
        + r")\s*"
        r"(pieces|units|copies|pairs)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"only\s+([\d,]+)\s*"
        r"(pieces|units|copies|available|made|"
        r"produced)",
        re.IGNORECASE,
    ),
    re.compile(
        r"([\d,]+)\s*(?:pieces|units|copies)"
        r"\s+(?:only|limited)",
        re.IGNORECASE,
    ),
]


def find_limited_quantity(text):
    for pattern in LIMITED_QUANTITY_PATTERNS:
        for match in pattern.finditer(text):
            if is_locally_negated(
                text, match.start()
            ):
                continue

            if has_unlimited_override(
                _context_window(
                    text,
                    match.start(),
                    match.end(),
                )
            ):
                continue

            raw = match.group(1).replace(",", "")
            value = word_to_number(raw)

            if value is None:
                continue

            return {
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(0),
            }

    return None


PURCHASE_LIMIT_PATTERNS = [
    re.compile(
        r"limit\s+(?:of\s+)?(\d+)\s*per\s*"
        r"(?:customer|order|household|person)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:maximum|max)\s+of\s+(\d+)\s*per\s*"
        r"(?:customer|order|household|person)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+)\s*per\s*"
        r"(?:customer|order|household|person)"
        r"\s*(?:limit)?",
        re.IGNORECASE,
    ),
]


def find_purchase_limit(text):
    for pattern in PURCHASE_LIMIT_PATTERNS:
        for match in pattern.finditer(text):
            if is_locally_negated(
                text, match.start()
            ):
                continue

            try:
                value = int(match.group(1))
            except ValueError:
                continue

            return {
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(0),
            }

    return None


PACK_QUANTITY_PATTERN = re.compile(
    r"(?:receive|get|includes?)\s+"
    r"("
    + "|".join(WORD_NUMBERS)
    + r"|\d+)\s+"
    r"(?:exclusive\s+|promotional\s+)*"
    r"(?:promotional\s+)?"
    r"(?:card\s+)?packs?",
    re.IGNORECASE,
)


def find_pack_quantity(text):
    match = PACK_QUANTITY_PATTERN.search(text)

    if not match:
        return None

    value = word_to_number(match.group(1))

    if value is None:
        return None

    return {
        "value": value,
        "start": match.start(),
        "end": match.end(),
        "matched_text": match.group(0),
    }


NUMBERED_PATTERNS = [
    re.compile(
        r"\bindividually numbered\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnumbered\b", re.IGNORECASE),
    re.compile(r"#\d+\s*/\s*\d+"),
    re.compile(
        r"\bserial number(?:ed)?\b",
        re.IGNORECASE,
    ),
]


def find_numbered_release(text):
    for pattern in NUMBERED_PATTERNS:
        match = pattern.search(text)

        if not match:
            continue

        if is_locally_negated(text, match.start()):
            continue

        return {
            "start": match.start(),
            "end": match.end(),
            "matched_text": match.group(0),
        }

    return None


# ---------------------------------------------------------------
# Date / time / duration extraction
# ---------------------------------------------------------------

MONTH_NAMES = (
    "January|February|March|April|May|June|"
    "July|August|September|October|November|"
    "December"
)

DATE_PATTERN = re.compile(
    r"\b(" + MONTH_NAMES + r")\s+(\d{1,2})"
    r"(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)


def find_dates(text):
    results = []

    for match in DATE_PATTERN.finditer(text):
        results.append({
            "start": match.start(),
            "end": match.end(),
            "month": match.group(1),
            "day": match.group(2),
            "year": match.group(3),
            "matched_text": match.group(0),
        })

    return results


PURCHASE_WINDOW_PATTERN = re.compile(
    r"\b("
    + MONTH_NAMES
    + r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"\s+(?:through|to|until|-|–)\s+"
    r"(?:("
    + MONTH_NAMES
    + r")\s+)?(\d{1,2})(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)


def find_purchase_window(text):
    match = PURCHASE_WINDOW_PATTERN.search(text)

    if not match:
        return None

    start_month = match.group(1)
    start_day = match.group(2)
    end_month = match.group(3) or start_month
    end_day = match.group(4)

    return {
        "start": match.start(),
        "end": match.end(),
        "matched_text": match.group(0),
        "window_start": (
            f"{start_month} {start_day}"
        ),
        "window_end": f"{end_month} {end_day}",
    }


DURATION_PATTERN = re.compile(
    r"within\s+(\d+)\s*"
    r"(minutes?|hours?|days?|seconds?)",
    re.IGNORECASE,
)


def find_sellout_duration(text):
    match = DURATION_PATTERN.search(text)

    if not match:
        return None

    return {
        "start": match.start(),
        "end": match.end(),
        "matched_text": match.group(0),
        "value": int(match.group(1)),
        "unit": match.group(2).lower().rstrip(
            "s"
        ),
    }


TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*"
    r"(AM|PM|am|pm)\b(?:\s*[A-Z]{2,4}\b)?"
)


def find_release_time(text):
    match = TIME_PATTERN.search(text)

    if not match:
        return None

    return {
        "start": match.start(),
        "end": match.end(),
        "matched_text": match.group(0),
    }


# ---------------------------------------------------------------
# Collaboration extraction
# ---------------------------------------------------------------

_NAME_PART = (
    r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'&]+"
    r"(?:[^\S\n]+[A-Za-zÀ-ÖØ-öø-ÿ0-9'&]+){0,3}"
)

COLLAB_SEPARATOR_PATTERN = re.compile(
    r"(" + _NAME_PART + r")"
    r"\s*(?:×|x|X)\s*"
    r"(" + _NAME_PART + r")"
)

COLLAB_AND_LAUNCHED_PATTERN = re.compile(
    r"(" + _NAME_PART + r")"
    r"\s+and\s+"
    r"(" + _NAME_PART + r")"
    r"\s+(?:launched|announced|revealed|"
    r"unveiled)\b.{0,60}?collaboration",
    re.IGNORECASE,
)

COLLAB_SINGLE_SIDE_PATTERNS = [
    re.compile(
        r"(?:in\s+)?collaboration with\s+"
        r"(" + _NAME_PART + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"teams? up with\s+(" + _NAME_PART + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"partner(?:ed|ship)? with\s+"
        r"(" + _NAME_PART + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"crossover with\s+(" + _NAME_PART + r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"special campaign with\s+"
        r"(" + _NAME_PART + r")",
        re.IGNORECASE,
    ),
]

COLLABORATION_KEYWORDS = [
    "collaboration",
    "collab",
    "crossover",
    "teamed up",
    "teams up",
    "team up",
    "partnered",
    "partnership",
    "special campaign",
]


LEADING_NAME_ARTICLES = {"the", "a", "an", "this", "that"}

TRAILING_NAME_STOPWORDS = {
    "for", "during", "at", "starting", "beginning", "from", "to",
    "with", "featuring", "on", "of", "and",
    "campaign", "collection", "event", "launch", "collaboration",
}


def _clean_name_span(text):
    """
    _NAME_PART is deliberately greedy (up to 4 words) so it can catch
    multi-word brand names, but that also lets it swallow a leading
    article ("The Sanrio") or trailing filler words that happened to
    follow the real name ("Round1 for a summer"). Strip both: drop a
    leading article/demonstrative outright, then keep only the
    contiguous run of words before the first connector-ish stopword.
    """
    words = text.split()

    while words and words[0].lower() in LEADING_NAME_ARTICLES:
        words.pop(0)

    trimmed = []

    for word in words:
        if word.lower() in TRAILING_NAME_STOPWORDS:
            break

        trimmed.append(word)

    return " ".join(trimmed)


def _looks_like_proper_noun_phrase(text):
    text = text.strip()

    if not text:
        return False

    first_alpha = next(
        (
            character
            for character in text
            if character.isalpha()
        ),
        None,
    )

    if first_alpha is None:
        return False

    return first_alpha.isupper()


def find_collaboration(text):
    """
    Returns {"left": str, "right": str|None, "start", "end",
    "matched_text"} for the strongest collaboration match found, or
    None. `right` may be None for single-sided patterns (e.g.
    "collaboration with Round1") where only one partner name is
    stated explicitly in the matched phrase.
    """
    match = COLLAB_AND_LAUNCHED_PATTERN.search(
        text
    )

    if match:
        left = _clean_name_span(match.group(1))
        right = _clean_name_span(match.group(2))

        if _looks_like_proper_noun_phrase(
            left
        ) and _looks_like_proper_noun_phrase(
            right
        ) and not is_locally_negated(
            text, match.start()
        ):
            return {
                "left": left,
                "right": right,
                "start": match.start(),
                "end": match.end(),
                "matched_text": match.group(0),
            }

    for match in (
        COLLAB_SEPARATOR_PATTERN.finditer(text)
    ):
        left = _clean_name_span(match.group(1))
        right = _clean_name_span(match.group(2))

        if not (
            _looks_like_proper_noun_phrase(left)
            and _looks_like_proper_noun_phrase(
                right
            )
        ):
            continue

        if is_locally_negated(
            text, match.start()
        ):
            continue

        return {
            "left": left,
            "right": right,
            "start": match.start(),
            "end": match.end(),
            "matched_text": match.group(0),
        }

    for pattern in COLLAB_SINGLE_SIDE_PATTERNS:
        match = pattern.search(text)

        if not match:
            continue

        if is_locally_negated(
            text, match.start()
        ):
            continue

        partner = _clean_name_span(
            match.group(1)
        ).rstrip(".,")

        if not partner:
            continue

        return {
            "left": None,
            "right": partner,
            "start": match.start(),
            "end": match.end(),
            "matched_text": match.group(0),
        }

    return None


def has_collaboration_keyword(text):
    lowered = text.lower()

    return any(
        keyword in lowered
        for keyword in COLLABORATION_KEYWORDS
    )
