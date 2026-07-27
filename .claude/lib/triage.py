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
    # `email@e.upgrade.com`, `email@savings.lendingtree.com`. Nobody is named
    # email@ either, and both of these were reaching ACT as first-time humans.
    "email", "mail", "inspiration", "digest", "reply", "invite", "invites",
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
    # Send-only platforms: a domain that exists to deliver marketing, where the
    # local part is a brand name rather than a person. Structural rules below
    # cannot catch these because there is nothing structural to catch.
    "safeopt.com", "lensa.com", "wellfound.com", "polymarket.com",
]

# Subdomain labels that mean "this is the mail arm of a domain". Compared as
# whole tokens against each label to the LEFT of the registrable domain, after
# splitting on - and _ — so `us-news.comms.adidas.com` yields {us, news, comms}
# and matches on `news`, while `example.com` yields {example} and matches
# nothing. An earlier version substring-matched the whole domain and filed
# every human at example.com as noise, because "e." appears inside it.
BULK_SUBDOMAIN_TOKENS = {
    "e", "em", "m", "mail", "email", "mailer", "news", "newsletter", "letter",
    "alert", "alerts", "notify", "notifications", "updates", "info", "reply",
    "mkt", "marketing", "promo", "promos", "offers", "savings", "deals",
    "link", "click", "go", "tm", "t", "account", "accounts", "hey", "learn",
    "comms", "send", "sender", "delivery", "campaign", "campaigns", "cmail",
}

# Two-part public suffixes, so the registrable name of `sura.com.co` is `sura`
# and not `com`. Not exhaustive — just the ones that show up in Joel's mail.
MULTIPART_SUFFIXES = {
    "com.co", "com.mx", "com.br", "com.ar", "com.au", "co.uk", "org.uk",
    "co.jp", "co.kr", "com.tr", "com.sg", "co.in", "com.pe", "cl.co",
}

# Money / legal / deadline language — pushes toward ACT.
#
# Matched as whole words (see _hits), which is why "payment" is not here on its
# own: it matched "Get ahead of your monthly payments" from a loan advertiser.
# Bare "agreement" is gone for the same reason — it matched a gym's "copy of
# your agreement for your records". Actionable money says WHICH action.
ACT_TERMS = [
    "invoice", "past due", "overdue", "payment due", "payment failed",
    "payment declined", "wire", "deposit", "refund", "outstanding balance",
    "amount due", "signature", "signature request", "please sign", "docusign",
    "signnow", "countersign", "deadline", "expire", "expires", "expiring",
    "urgent", "final notice", "suspend", "suspended", "terminated", "quota",
    "unable to send", "action required", "verify your", "respond by",
    "awaiting your", "needs your approval", "last chance to",
    # Appointments are commitments. Calendar.app holds only holidays, so
    # confirmation email is Joel's real calendar — see the Optic Gold thread.
    "appointment", "you are scheduled", "mark your calendar", "reschedule",
]

# Regex-shaped ACT signals that a word list cannot express.
ACT_PATTERNS = [
    # "storage is 87% full", "97% of your quota". The Google One warning said
    # neither "quota" nor "unable to send" and was filed NOISE.
    (r"\b\d{1,3}\s*%\s*(?:full|used|of your)", "storage or quota threshold"),
    (r"\b(?:run(?:ning)? )?out of storage\b", "out of storage"),
    (r"\bstorage is (?:almost )?full\b", "storage full"),
    # A date plus a time, in a message short enough to be a booking.
    (r"\b(?:on |for )?(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+\d{1,2}[/ ]",
     "day-and-date booking"),
]

# Account-takeover and credential-change language. Checked BEFORE the FYI list,
# because "confirmation" is an FYI word and "Your Apple account confirmation
# request was confirmed ... from Baghdad Iraq" is not an FYI message. Credential
# changes are manual action #5; the system never resolves these, only escalates.
SECURITY_TERMS = [
    "if this was not you", "if this wasn't you", "if you did not", "if it wasn't you",
    "was confirmed on an", "unrecognized device", "unfamiliar device",
    "new device signed in", "unusual activity", "suspicious activity",
    "suspicious sign-in", "password was changed", "password was reset",
    "recovery email was changed", "recovery phone was changed",
    "two-factor was disabled", "2-step verification was", "someone else has your",
    "your account was accessed",
]

# Real information, no action needed.
FYI_TERMS = [
    "receipt", "confirmation", "confirmed", "shipped", "delivered", "statement",
    "report", "summary", "security alert", "new sign-in",
    "for your records", "welcome to", "you shared", "sign in to",
    # "digest" and "recap" were here and promoted every Skool community digest
    # out of NOISE. They describe a message's shape, not whether it informs.
    # Spanish-language document delivery — SURA sends electronic credit notes.
    "nota credito", "nota de credito", "factura", "comprobante",
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
    """Read correction lines. Malformed lines are skipped, not guessed at.

    Returned newest-first. The file is append-only, so a matcher Joel corrected
    twice appears twice; the most recent correction must win. Iterating in file
    order gave the oldest rule precedence, which meant changing your mind about a
    sender had no effect.
    """
    found = []
    for i, line in enumerate(text.splitlines()):
        m = CORRECTION_RE.match(line)
        if not m:
            continue
        found.append((m.group("date") or "", i, Rule(
            m.group("kind").lower(),
            m.group("value").strip(),
            m.group("bucket").upper(),
            (m.group("reason") or "").strip(),
            m.group("date") or "",
        )))
    # Newest date first; for equal or missing dates, later in the file wins.
    found.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [r for _, _, r in found]


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


def _registrable(domain):
    """Split a domain into (subdomain_labels, registrable_name).

    `us-news.comms.adidas.com` -> (['us-news', 'comms'], 'adidas')
    `sura.com.co`              -> ([], 'sura')
    `patrickdang.com`          -> ([], 'patrickdang')
    """
    labels = [l for l in (domain or "").split(".") if l]
    if len(labels) < 2:
        return [], (labels[0] if labels else "")
    suffix_len = 2 if ".".join(labels[-2:]) in MULTIPART_SUFFIXES else 1
    name_idx = len(labels) - suffix_len - 1
    if name_idx < 0:
        return [], labels[0]
    return labels[:name_idx], labels[name_idx]


def _tokens(label):
    return {t for t in re.split(r"[-_]+", label) if t}


def looks_like_bulk(sender):
    a = _addr(sender)
    local = a.split("@")[0] if "@" in a else a
    domain = _domain(sender)

    if any(b in local for b in BULK_LOCAL):
        return True
    if any(h in domain for h in BULK_DOMAIN_HINTS):
        return True

    subs, name = _registrable(domain)

    # The mail arm of a domain: any subdomain label that is bulk-mail machinery.
    for label in subs:
        if _tokens(label) & BULK_SUBDOMAIN_TOKENS:
            return True
        # Generated sending shards: mp1, e2, s3, m10.
        if re.fullmatch(r"[a-z]{0,3}\d{1,3}", label):
            return True

    # A brand mailing as itself: adidas@...adidas.com, ebay@ebay.com,
    # Coursera@m.learn.coursera.org, suracomunicaciones@sura.com.co.
    #
    # Guarded two ways so it cannot swallow humans. A dot in the local part
    # means a person's name (sura.rodriguez@sura.com.co stays human), and the
    # registrable name must be long enough that the containment is meaningful —
    # otherwise `jason@rltrs.co` would match on a three-letter company.
    if name and len(name) >= 4 and "." not in local and name in local:
        return True

    # A local part with a long digit run is almost always a generated bulk address.
    if re.search(r"\d{6,}", local):
        return True
    return False


def _hits(terms, blob):
    """Whole-word matches only.

    Substring matching is why "sign " matched "Sign in with Google" and promoted
    a routine OAuth notice to ACT. Terms containing spaces are matched as
    phrases with boundaries at each end.
    """
    out = []
    for t in terms:
        if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", blob):
            out.append(t)
    return out


def _pattern_hits(blob):
    return [why for rx, why in ACT_PATTERNS if re.search(rx, blob)]


def severity(msg):
    """How loudly an ACT item should land. 'security' outranks 'high'.

    Kept separate from the bucket so the dashboard can rank within ACT without
    the classifier needing a fifth bucket.
    """
    blob = " ".join([
        (msg.get("sender") or "").lower(),
        (msg.get("subject") or "").lower(),
        (msg.get("snippet") or "").lower(),
    ])
    if _hits(SECURITY_TERMS, blob):
        return "security"
    money_or_legal = _hits(["invoice", "past due", "overdue", "payment due",
                            "wire", "deposit", "refund", "amount due",
                            "final notice", "suspend", "suspended", "terminated",
                            "deadline", "signature request"], blob)
    if money_or_legal:
        return "high"
    return "normal"


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

    # 2b — account takeover and credential changes.
    #
    # Above every other heuristic and above the bulk check, because these
    # arrive from noreply@ addresses and use vocabulary that reads as FYI.
    # "Your Apple account confirmation request was confirmed on an iPhone 16
    # from the location of Baghdad Iraq" was filed FYI on the word
    # "confirmation" — the one message in the inbox that could not wait.
    sec_hits = _hits(SECURITY_TERMS, blob)
    if sec_hits:
        return ACT, f"security: {sec_hits[0]}"

    bulk = looks_like_bulk(sender)

    # A human who has never written before is always ACT (email-rules.md).
    # Only as trustworthy as `known` is complete — an empty known-senders set
    # makes every sender first-time, which is how eleven newsletters reached
    # ACT. Seed it from sent mail; see save_known_senders.
    if not bulk and addr and addr not in known:
        return ACT, "first-time human sender"

    # 3 — heuristics
    act_hits = _hits(ACT_TERMS, blob) + _pattern_hits(blob)
    fyi_hits = _hits(FYI_TERMS, blob)

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
