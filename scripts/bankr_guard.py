import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class BankrIntent:
    is_write: bool
    hits: List[str]


_WRITE_PATTERNS = [
    # Direct asset movement / tx creation
    r"\bsend\b",
    r"\btransfer\b",
    r"\bwithdraw\b",
    r"\bdeposit\b",
    r"\bbridge\b",
    r"\bapprove\b",
    r"\bsign\b",
    r"\bsubmit\b",
    r"\btransaction\b",
    r"\btx\b",
    # Trading
    r"\bbuy\b",
    r"\bsell\b",
    r"\bswap\b",
    r"\btrade\b",
    r"\blimit\s+order\b",
    r"\bmarket\s+order\b",
    # DeFi actions
    r"\bstake\b",
    r"\bunstake\b",
    r"\blend\b",
    r"\bborrow\b",
    r"\brepay\b",
    r"\bclaim\b",
    r"\bmint\b",
    r"\bburn\b",
]


def classify_bankr_intent(text: str) -> BankrIntent:
    """
    Heuristic guard: treat any prompt that appears to request on-chain actions
    (sending funds, swaps, approvals, signing/submitting txs) as "write intent".

    This is intentionally conservative. ORION should only allow write intents
    with explicit user confirmation.
    """
    raw = (text or "").strip()
    if not raw:
        return BankrIntent(is_write=False, hits=[])

    # Ignore escaped tokens like \send, so ORION can discuss these words safely.
    # Convert "\word" into "word_escaped" so word-boundary patterns won't match.
    cleaned = re.sub(r"\\([A-Za-z]{2,})\b", r"\1_escaped", raw)
    lower = cleaned.lower()

    hits: List[str] = []
    for pat in _WRITE_PATTERNS:
        if re.search(pat, lower, flags=re.IGNORECASE):
            # Store the canonical keyword-ish token for messaging.
            hits.append(pat.strip(r"\b").replace(r"\s+", " "))

    # Dedupe, preserve order
    seen = set()
    ordered: List[str] = []
    for h in hits:
        if h in seen:
            continue
        seen.add(h)
        ordered.append(h)

    return BankrIntent(is_write=bool(ordered), hits=ordered)
