"""Email classifier: ACT / FYI / NOISE / UNSURE.

Pure functions over message metadata. No network, no MCP, no side effects — so it
can be tested exhaustively offline and the same input always yields the same bucket.

Precedence, highest first:

  1. Corrections in memory/email-rules.md   — Joel said so, and Joel wins
  2. Always-ACT overrides                   — accountant, lawyer, bank, first-time human
  3. Heuristics                             — bulk-sender and content signals
  4. UNSURE                                 — when signals conflict, never guess

The hard limits from email-rules.md are structural, not advisory: this module has no
code path that sends, replies, deletes, or unsubscribes. It returns a label.
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RULES = os.path.join(ROOT, "memory", "email-rules.md")
KNOWN_SENDERS = os.path.join(ROOT, "state", "known-senders.json")

ACT, FYI, NOISE, UNSURE = "ACT", "FYI", "NOISE", "UNSURE"
BUCKETS = (ACT, FYI, NOISE, UNSURE)

# Senders that are always ACT no matter what the heuristics say.
ALWAYS_ACT_TERMS = [
    "accountant", "cpa", "bookkeep", "tax",
    "lawyer", "attorney", "legal", "counsel",
    "bank", "chase", "wells fargo", "bofa", "bankofamerica", "citi",
]

# Bulk-mail machinery. Strong NOISE signal in the local part of an address.
BULK_LOCAL = [
    "noreply", "no-reply", "donotreply", "do-not-reply", "notifications",
    "notification", "updates", "newsletter", "mailer", "bounce", "alerts",
    "alert", "info", "hello", "team", "support", "marketing", "news",
    # Role addresses. Nobody is named admin@ — treating these as first-time humans
    # promoted every SaaS announcement to ACT.
    "admin", "billing", "sales", "contact", "help", "service", "services",
    "office", "careers", "jobs", "hr", "accounts-", "member", "welcome",
]

# Domains whose mail is structurally bulk. Matched as substrings, so every entry
# here must be specific enough that it cannot appear inside an ordinary domain.
BULK_DOMAIN_HINTS = [
    "linkedin.com", "indeed.com", "jobalert", "glassdoor", "ziprecruiter",
    "skool.com", "beehiiv.com", "substack.com", "mailchimp", "sendgrid.net",
    "tiktok.com", "ebay.com", "equifax.com", "creditsesame.com", "kalshi.com",
    "newsletter", "refer.io", "icims.com",
]

# Bulk-mail subdomain prefixes: `e.equifax.com`, `mail.beehiiv.com`, `tm.openai.com`.
# Matched against the FIRST domain label only — as a substring these would match
# far too much (an earlier version matched "e." inside "example.com" and filed
# every human at that domain as noise).
BULK_SUBDOMAINS = {
    "e", "em", "mail", "email", "mailer", "news", "newsletter", "alert", "alerts",
    "notify", "notifications", "updates", "info", "reply", "mkt", "marketing",
    "link", "click", "go", "tm", "t", "account", "accounts", "hey",
}

# Money / legal / deadline language — pushes toward ACT.
ACT_TERMS = [
    "invoice", "payment", "past due", "overdue", "wire", "deposit", "refund",
    "contract", "agreement", "signature", "sign ", "docusign", "signnow",
    "deadline", "expire", "expires", "expiring", "urgent", "final notice", "suspend",
    "terminated", "quota", "unable to send", "action required", "verify your",
]

# Real information, no action needed.
FYI_TERMS = [
    "receipt", "confirmation", "confirmed", "shipped", "delivered", "statement",
    "report", "summary", "digest", "recap", "security alert", "new sign-in",
]


class Rule:
    """One correction line from memory/email-rules.md."""

    def __init__(self, kind, value, bucket, reason="", date=""):
        self.kind = kind
        self.value = value.lower()
        self.bucket = bucket
        self.reason = reason
        self.date = date

    def matches(self, msg):
        sender = (msg.get("sender") or "").lower()
        subject = (msg.get("subject") or "").lower()
        snippet = (msg.get("snippet") or "").lower()
        if self.kind == "sender":
            return self.value in sender
        if self.kind == "domain":
            return sender.endswith(self.value) or ("@" + self.value) in sender \
                or ("." + self.value) in sender
        if self.kind == "subject":
            return self.value in subject
        if self.kind == "contains":
            return self.value in subject or self.value in snippet or self.value in sender
        return False

    def __repr__(self):
        return f"Rule({self.kind}:{self.value} -> {self.bucket})"


# Correction lines look like:
#   - 2026-07-26 | domain:skool.com | NOISE | community notifications, never actionable
CORRECTION_RE = re.compile(
    r"^\s*[-*]\s*(?P<date>\d{4}-\d{2}-\d{2})?\s*\|?\s*"
    r"(?P<kind>sender|domain|subject|contains)\s*:\s*(?P<value>[^|]+?)\s*\|\s*"
    r"(?P<bucket>ACT|FYI|NOISE|UNSURE)\s*(?:\|\s*(?P<reason>.*))?$",
    re.IGNORECASE,
)


def parse_rules(text):
    """Read correction lines. Malformed lines are skipped, not guessed at."""
    rules = []
    for line in text.splitlines():
        m = CORRECTION_RE.match(line)
        if not m:
            continue
        rules.append(Rule(
            m.group("kind").lower(),
            m.group("value").strip(),
            m.group("bucket").upper(),
            (m.group("reason") or "").strip(),
            m.group("date") or "",
        ))
    return rules


def load_rules(path=RULES):
    try:
        with open(path) as f:
            return parse_rules(f.read())
    except FileNotFoundError:
        return []


def load_known_senders(path=KNOWN_SENDERS):
    try:
        with open(path) as f:
            return set(json.load(f).get("senders", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_known_senders(senders, path=KNOWN_SENDERS):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"senders": sorted(senders)}, f, indent=2)
        f.write("\n")


def _addr(sender):
    m = re.search(r"[\w.+-]+@[\w.-]+", sender or "")
    return m.group(0).lower() if m else (sender or "").lower()


def _domain(sender):
    a = _addr(sender)
    return a.split("@")[-1] if "@" in a else ""


def looks_like_bulk(sender):
    a = _addr(sender)
    local = a.split("@")[0] if "@" in a else a
    domain = _domain(sender)
    if any(b in local for b in BULK_LOCAL):
        return True
    if any(h in domain for h in BULK_DOMAIN_HINTS):
        return True
    labels = domain.split(".")
    if len(labels) > 2 and labels[0] in BULK_SUBDOMAINS:
        return True
    # A local part with a long digit run is almost always a generated bulk address.
    if re.search(r"\d{6,}", local):
        return True
    return False


def classify(msg, rules=None, known_senders=None):
    """Return (bucket, reason). Never raises, never mutates its inputs."""
    rules = rules if rules is not None else []
    known = known_senders if known_senders is not None else set()

    sender = msg.get("sender") or ""
    subject = (msg.get("subject") or "").lower()
    snippet = (msg.get("snippet") or "").lower()
    blob = f"{sender.lower()} {subject} {snippet}"
    addr = _addr(sender)

    # 1 — corrections win outright
    for r in rules:
        if r.matches(msg):
            return r.bucket, f"correction: {r.kind}:{r.value}" + (
                f" — {r.reason}" if r.reason else "")

    # 2 — always-ACT overrides
    for term in ALWAYS_ACT_TERMS:
        if term in blob:
            return ACT, f"always-ACT term: {term}"

    bulk = looks_like_bulk(sender)

    # A human who has never written before is always ACT (email-rules.md).
    if not bulk and addr and addr not in known:
        return ACT, "first-time human sender"

    # 3 — heuristics
    act_hits = [t for t in ACT_TERMS if t in blob]
    fyi_hits = [t for t in FYI_TERMS if t in blob]

    if bulk:
        # Bulk mail can still be genuinely actionable — a quota cutoff or an
        # expiring credential arrives from a noreply@ address.
        if act_hits:
            return ACT, f"bulk sender but actionable: {act_hits[0]}"
        if fyi_hits:
            return FYI, f"bulk informational: {fyi_hits[0]}"
        return NOISE, "bulk sender, no actionable signal"

    if act_hits:
        return ACT, f"actionable: {act_hits[0]}"
    if fyi_hits:
        return FYI, f"informational: {fyi_hits[0]}"

    # 4 — known human, nothing decisive. Never guess.
    return UNSURE, "known human sender, no decisive signal"


def triage(messages, rules=None, known_senders=None):
    """Classify a batch. Returns list of dicts with bucket + reason attached."""
    rules = rules if rules is not None else load_rules()
    known = known_senders if known_senders is not None else load_known_senders()
    out = []
    for m in messages:
        bucket, reason = classify(m, rules, known)
        out.append(dict(m, bucket=bucket, reason=reason))
    return out


def summarize(results):
    counts = {b: 0 for b in BUCKETS}
    for r in results:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
    return counts


MODE_PATH = os.path.join(ROOT, "state", "triage-mode.json")
SHADOW_DAYS = 14


def mode(path=MODE_PATH, today=None):
    """Are we still in the label-only window?

    PHASES.md: "First two weeks: label only, archive nothing. Show what would have
    happened, then turn it on." Archiving stays off until the window elapses AND
    Joel flips `archive_enabled`. Time passing alone is not consent.
    """
    import datetime
    today = today or datetime.date.today()
    try:
        with open(path) as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"archive": False, "reason": "no triage-mode.json — label-only",
                "days_left": SHADOW_DAYS, "started": None}

    started = cfg.get("started")
    enabled = bool(cfg.get("archive_enabled"))
    try:
        start = datetime.date.fromisoformat(started) if started else None
    except (ValueError, TypeError):
        start = None

    if start is None:
        return {"archive": False, "reason": "no start date recorded — label-only",
                "days_left": SHADOW_DAYS, "started": None}

    elapsed = (today - start).days
    left = max(0, SHADOW_DAYS - elapsed)
    if left > 0:
        return {"archive": False, "started": started, "days_left": left,
                "reason": f"label-only window: {left} day(s) left of {SHADOW_DAYS}"}
    if not enabled:
        return {"archive": False, "started": started, "days_left": 0,
                "reason": "window elapsed, but archive_enabled is false — "
                          "Joel has not turned archiving on"}
    return {"archive": True, "started": started, "days_left": 0,
            "reason": "window elapsed and archiving enabled"}


def format_correction(kind, value, bucket, reason, date):
    """Render a correction line for appending to memory/email-rules.md."""
    if kind not in ("sender", "domain", "subject", "contains"):
        raise ValueError(f"unknown matcher: {kind}")
    if bucket not in BUCKETS:
        raise ValueError(f"unknown bucket: {bucket}")
    return f"- {date} | {kind}:{value} | {bucket} | {reason}"
