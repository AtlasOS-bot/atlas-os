"""
Atlas v21 - Module 4: conservative identity matching.

Decides whether two candidate CollectorOpportunity drafts (each built
from one source by Module 2) describe the SAME real-world opportunity,
so Module 4 can merge them instead of creating duplicates or,
conversely, avoid merging genuinely different products that just
happen to share a franchise.

Deliberately conservative: with too little overlapping identity
evidence to compare, two drafts are treated as NOT matching rather
than guessed into the same group.
"""

from collector_intelligence.normalize import normalize_text


IDENTITY_FIELDS = [
    "product_name",
    "brand",
    "franchise",
    "collaboration_partner",
    "retailer",
    "release_date",
    "edition_name",
    "release_region",
    "set_or_series",
]

# Fields whose presence alone isn't enough to call two drafts a match
# (too generic - nearly every source in a batch might share these).
_WEAK_FIELDS = {"brand", "franchise"}


def identity_signature(draft):
    return {
        field_name: normalize_text(getattr(draft, field_name, None)) or None
        for field_name in IDENTITY_FIELDS
    }


def _comparable_fields(sig_a, sig_b):
    return [
        field_name
        for field_name in IDENTITY_FIELDS
        if sig_a.get(field_name) and sig_b.get(field_name)
    ]


def _fields_match(value_a, value_b):
    """
    Exact match, or one value is a substring of the other. Module 2's
    entity extraction is regex-based and sometimes over-captures a
    trailing word or two (e.g. "Round1 promotional packs are" instead
    of "Round1") - requiring exact string equality here would wrongly
    split a single real-world opportunity into separate groups over
    that noise. A substring relationship is still strong evidence of
    the same entity.
    """
    if value_a == value_b:
        return True

    if not value_a or not value_b:
        return False

    return value_a in value_b or value_b in value_a


def identity_similarity(sig_a, sig_b):
    """
    Fraction of mutually-known identity fields that agree. Returns 0.0
    if there isn't enough overlap to judge at all.
    """
    comparable = _comparable_fields(sig_a, sig_b)

    if not comparable:
        return 0.0

    matches = sum(
        1 for field_name in comparable
        if _fields_match(sig_a[field_name], sig_b[field_name])
    )

    return matches / len(comparable)


def same_opportunity(draft_a, draft_b, threshold=0.6):
    """
    True only when there's enough overlapping, specific identity
    evidence AND it agrees strongly enough. Sharing only a franchise
    or brand is never sufficient on its own - "One Piece x Round1
    promotional packs" and "One Piece booster box" must stay separate.
    """
    sig_a = identity_signature(draft_a)
    sig_b = identity_signature(draft_b)

    comparable = _comparable_fields(sig_a, sig_b)

    if len(comparable) < 2:
        return False

    if set(comparable) <= _WEAK_FIELDS:
        return False

    return identity_similarity(sig_a, sig_b) >= threshold


def group_drafts(drafts, threshold=0.6):
    """
    Partitions drafts (a list of CollectorOpportunity) into groups of
    indices describing the same opportunity, via pairwise comparison
    across the whole batch (a union-find over same_opportunity()
    edges) - so the resulting partition never depends on input order,
    only on the pairwise relationships themselves.
    """
    n = len(drafts)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for i in range(n):
        for j in range(i + 1, n):
            if same_opportunity(drafts[i], drafts[j], threshold):
                union(i, j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    return sorted(groups.values(), key=min)
