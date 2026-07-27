"""The only module that knows the memory/projects.md format.

Nothing else parses that file. If the format changes, it changes here.

Format:

    ## Active
    ### <project name>
    - status: <text>
    - next action: <text>
    - blocked by: <text>
    - last movement: <YYYY-MM-DD>

Sections are Active / Dormant / Done. A `###` block whose body doesn't parse is
kept verbatim as a malformed entry rather than dropped — silently losing a project
is worse than showing a broken one.
"""

import datetime
import re

FIELDS = ["status", "next action", "blocked by", "last movement"]

# Optional evidence fields. Rendered only when set, so existing entries keep
# their exact shape. `last movement` is hand-written and therefore decays into
# "Joel forgot to edit this file"; these let movement.py derive the real date.
#
#   - repos: ~/alivio-platform, ~/alivio-search-partners
#   - linear: Alivio Platform & Website
OPTIONAL_FIELDS = ["repos", "linear"]
ALL_FIELDS = FIELDS + OPTIONAL_FIELDS
SECTIONS = ["Active", "Dormant", "Done"]

# Projects with no movement in this many days are flagged stale (PHASES.md: "red flag
# at 7+ days stale").
STALE_DAYS = 7


class Project:
    def __init__(self, name, section, fields=None, raw=None, malformed=False):
        self.name = name
        self.section = section
        self.fields = fields or {}
        self.raw = raw
        self.malformed = malformed

    @property
    def status(self):
        return self.fields.get("status", "")

    @property
    def next_action(self):
        return self.fields.get("next action", "")

    @property
    def blocked_by(self):
        return self.fields.get("blocked by", "")

    @property
    def last_movement(self):
        return self.fields.get("last movement", "")

    @property
    def repos(self):
        """Filesystem paths whose git history evidences movement."""
        raw = self.fields.get("repos", "")
        return [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def linear(self):
        """Linear project name whose issue activity evidences movement."""
        return self.fields.get("linear", "").strip()

    def days_stale(self, today=None):
        """Days since last movement, or None if the date is missing/unparseable."""
        raw = self.last_movement.strip()
        if not raw:
            return None
        m = re.search(r"\d{4}-\d{2}-\d{2}", raw)
        if not m:
            return None
        try:
            d = datetime.date.fromisoformat(m.group(0))
        except ValueError:
            return None
        today = today or datetime.date.today()
        return (today - d).days

    def is_stale(self, today=None):
        n = self.days_stale(today)
        return n is not None and n >= STALE_DAYS

    def is_blocked(self):
        v = self.blocked_by.strip().lower()
        return bool(v) and v not in ("nothing", "none", "-", "—", "n/a")

    def to_dict(self, today=None, movement=None):
        """Serialize for the dashboard.

        `movement` is an optional dict from movement.derive() carrying an
        observed date and where it came from. When present it decides staleness,
        because a git commit is evidence and a hand-typed date is a memory. The
        declared date is still reported so a drift between them is visible
        rather than silently overwritten.
        """
        declared_days = self.days_stale(today)
        effective_days, source, observed = declared_days, "declared", self.last_movement
        if movement and movement.get("days_stale") is not None:
            src = movement.get("source") or "derived"
            if declared_days is None or movement["days_stale"] < declared_days:
                # Evidence is more recent than the note. Evidence wins.
                effective_days = movement["days_stale"]
                source = src
                observed = movement.get("date") or observed
            elif movement["days_stale"] == declared_days:
                # The note was right. Worth saying — "declared" alone reads as
                # "nobody checked", and something did.
                source = f"confirmed by {src}"
        return {
            "name": self.name,
            "section": self.section,
            "status": self.status,
            "next_action": self.next_action,
            "blocked_by": self.blocked_by,
            "last_movement": observed,
            "declared_movement": self.last_movement,
            "movement_source": source,
            "days_stale": effective_days,
            "stale": effective_days is not None and effective_days >= STALE_DAYS,
            "blocked": self.is_blocked(),
            "malformed": self.malformed,
            "raw": self.raw,
        }


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def parse(text):
    """Parse projects.md content into a list of Project objects."""
    text = _strip_comments(text)
    projects = []
    section = None
    name = None
    body = []

    def flush():
        if name is None:
            return
        fields = {}
        leftovers = []
        for line in body:
            m = re.match(r"^\s*[-*]\s*([^:]+?)\s*:\s*(.*)$", line)
            if m and m.group(1).strip().lower() in ALL_FIELDS:
                fields[m.group(1).strip().lower()] = m.group(2).strip()
            elif line.strip():
                leftovers.append(line)
        raw = "\n".join([f"### {name}"] + body).rstrip()
        # A block is malformed if it carries none of the known fields but does have
        # content — i.e. someone wrote something we can't read.
        malformed = not fields and bool(leftovers)
        projects.append(
            Project(name, section or "Active", fields, raw=raw, malformed=malformed)
        )

    for line in text.splitlines():
        h2 = re.match(r"^##\s+(.+?)\s*$", line)
        h3 = re.match(r"^###\s+(.+?)\s*$", line)
        if h2 and not h3:
            flush()
            name, body = None, []
            title = h2.group(1).strip()
            section = title if title in SECTIONS else title
            continue
        if h3:
            flush()
            name, body = h3.group(1).strip(), []
            continue
        if name is not None:
            body.append(line)

    flush()
    return projects


def render(projects):
    """Serialize projects back to markdown. parse(render(p)) round-trips."""
    out = ["# Projects", ""]
    for section in SECTIONS:
        out.append(f"## {section}")
        out.append("")
        for p in [x for x in projects if x.section == section]:
            if p.malformed and p.raw:
                out.append(p.raw)
                out.append("")
                continue
            out.append(f"### {p.name}")
            for f in FIELDS:
                # rstrip so an empty field renders as "- status:" not "- status: ",
                # which keeps `raw` byte-stable across a round trip.
                out.append(f"- {f}: {p.fields.get(f, '')}".rstrip())
            # Optional fields appear only when set, so entries that don't use
            # them round-trip byte-for-byte.
            for f in OPTIONAL_FIELDS:
                if p.fields.get(f, "").strip():
                    out.append(f"- {f}: {p.fields[f]}".rstrip())
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def load(path):
    try:
        with open(path) as f:
            return parse(f.read())
    except FileNotFoundError:
        return []


def upsert(projects, name, section=None, **fields):
    """Add or update a project in place. Returns (projects, created: bool).

    Callers are responsible for getting Joel's confirmation first — new projects
    enter by explicit approval, never by inference.
    """
    known = {k.replace("_", " "): v for k, v in fields.items() if v is not None}
    for p in projects:
        if p.name.lower() == name.lower():
            p.fields.update(known)
            if section:
                p.section = section
            p.malformed = False
            return projects, False
    projects.append(Project(name, section or "Active", known))
    return projects, True
