"""The butler. ElevenLabs text-to-speech, cached and rate-limited.

Voice: George (JBFqnCBsd6RMkjVDRZzb) — british, middle-aged, "warm, captivating".
Alternate: Daniel (onwK4e9ZLuTAKqWW03F9), a colder broadcast read.

THE POLICY MATTERS MORE THAN THE VOICE. Joel enabled all four triggers,
including agent lifecycle, which is the chatty one. A butler that reads out
every tool call is one you mute on day one, and a muted butler is worth nothing
— so lifecycle announcements ship rate-limited by default. The cap is a floor to
raise once he knows how it feels, not a ceiling imposed on him.

Cap breaches are LOGGED, never silently dropped. That is the same "no silent
caps" rule the NEEDS ME overflow counter already follows: a system that quietly
withholds things teaches you to distrust it.

Audio is cached by sha1(voice + text), so a repeated line costs nothing. The key
lives in state/voice-config.json, gitignored, same pattern as push-config.json.
Everything degrades to silent-and-logged when the key is missing or the API
fails — the cockpit never blocks on audio.
"""

import datetime
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "state", "voice-config.json")
CACHE = os.path.join(ROOT, "state", "voice-cache")
SPEECH_LOG = os.path.join(ROOT, "state", "voice-log.jsonl")

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
TIMEOUT_S = 30

DEFAULTS = {
    "enabled": False,
    "api_key": None,
    "voice_id": "JBFqnCBsd6RMkjVDRZzb",     # George
    "model_id": "eleven_multilingual_v2",
    "triggers": {
        "on_demand": True,
        "morning_brief": True,
        "push_worthy": True,
        "agent_lifecycle": True,
    },
    # Lifecycle only. The other triggers are rare by construction.
    "lifecycle": {
        "min_runtime_s": 60,       # ignore agents that barely ran
        "max_per_hour": 6,
        "failures_beat_completions": True,
    },
    "_note": "api_key can be copied from ~/clara/.env.local. This file is "
             "gitignored; never commit a key.",
}


def load_config(path=None):
    path = path or CONFIG
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(path):
        try:
            with open(path) as f:
                user = json.load(f)
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def write_default_config(path=None):
    path = path or CONFIG
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(DEFAULTS, f, indent=2)
        f.write("\n")
    os.chmod(path, 0o600)
    return path


def _log(rec, path=None):
    path = path or SPEECH_LOG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rec = {"ts": datetime.datetime.now().astimezone().isoformat(), **rec}
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def cache_key(text, voice_id):
    return hashlib.sha1(f"{voice_id}|{text}".encode("utf-8")).hexdigest()[:20]


def cached_path(text, voice_id, cache=None):
    return os.path.join(cache or CACHE, cache_key(text, voice_id) + ".mp3")


def say(text, cfg=None, cache=None, _fetch=None):
    """Return {ok, path, cached, reason}. Never raises, never blocks the caller."""
    cfg = cfg or load_config()
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "empty text"}
    if not cfg.get("enabled"):
        return _log({"ok": False, "reason": "voice disabled in voice-config.json",
                     "text": text[:120]})
    key = cfg.get("api_key")
    if not key:
        return _log({"ok": False, "reason": "no api_key in state/voice-config.json",
                     "text": text[:120]})

    voice = cfg["voice_id"]
    path = cached_path(text, voice, cache)
    if os.path.exists(path):
        return _log({"ok": True, "path": path, "cached": True,
                     "text": text[:120]})

    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = json.dumps({"text": text, "model_id": cfg["model_id"]}).encode()
    req = urllib.request.Request(
        API.format(voice=voice), data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    try:
        fetch = _fetch or (lambda: urllib.request.urlopen(req, timeout=TIMEOUT_S).read())
        audio = fetch()
    except (urllib.error.URLError, OSError, ValueError) as e:
        return _log({"ok": False, "reason": f"tts failed: {e}", "text": text[:120]})
    if not audio:
        return _log({"ok": False, "reason": "empty audio", "text": text[:120]})
    with open(path, "wb") as f:
        f.write(audio)
    return _log({"ok": True, "path": path, "cached": False,
                 "bytes": len(audio), "text": text[:120]})


def play(path):
    """macOS afplay. Fire and forget — audio never blocks the cockpit."""
    try:
        subprocess.Popen(["afplay", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def speak(text, trigger="on_demand", cfg=None, **kw):
    """say() plus the trigger policy plus playback."""
    cfg = cfg or load_config()
    if not cfg["triggers"].get(trigger, False):
        return _log({"ok": False, "reason": f"trigger {trigger!r} is off",
                     "text": text[:120]})
    r = say(text, cfg, **kw)
    if r.get("ok"):
        r["played"] = play(r["path"])
    return r


# ── lifecycle rate limiting ──────────────────────────────────────────────

def _spoken_last_hour(now=None, path=None):
    path = path or SPEECH_LOG
    if not os.path.exists(path):
        return 0
    now = now or datetime.datetime.now().astimezone()
    cutoff = now - datetime.timedelta(hours=1)
    n = 0
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
                if not r.get("ok") or r.get("trigger") != "agent_lifecycle":
                    continue
                if datetime.datetime.fromisoformat(r["ts"]) >= cutoff:
                    n += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return n


def lifecycle_announce(events, cfg=None, now=None, **kw):
    """Announce agents finishing or failing, under a cap.

    `events` is [{name, outcome: 'finished'|'failed', runtime_s}].

    Failures beat completions when the cap binds — if only one thing can be
    said, it should be the one that went wrong. Everything suppressed is logged
    with the reason, because a cap that hides things silently is indistinguishable
    from a broken feature.
    """
    cfg = cfg or load_config()
    lc = cfg["lifecycle"]
    now = now or datetime.datetime.now().astimezone()

    eligible = [e for e in events
                if (e.get("runtime_s") or 0) >= lc["min_runtime_s"]]
    skipped_short = [e for e in events if e not in eligible]

    if lc.get("failures_beat_completions"):
        eligible.sort(key=lambda e: 0 if e.get("outcome") == "failed" else 1)

    already = _spoken_last_hour(now)
    room = max(0, lc["max_per_hour"] - already)
    to_say, suppressed = eligible[:room], eligible[room:]

    said = []
    for e in to_say:
        verb = "has finished" if e.get("outcome") == "finished" else "has failed"
        r = speak(f"{e['name']} {verb}.", "agent_lifecycle", cfg, **kw)
        r["trigger"] = "agent_lifecycle"
        _log({"ok": r.get("ok"), "trigger": "agent_lifecycle",
              "text": f"{e['name']} {verb}."})
        said.append(e)

    if suppressed or skipped_short:
        _log({"ok": False, "reason": "lifecycle cap or runtime floor",
              "suppressed": [e["name"] for e in suppressed],
              "too_short": [e["name"] for e in skipped_short],
              "cap": lc["max_per_hour"], "already_this_hour": already,
              "note": "logged rather than silently dropped"})

    return {"said": [e["name"] for e in said],
            "suppressed": [e["name"] for e in suppressed],
            "too_short": [e["name"] for e in skipped_short],
            "cap": lc["max_per_hour"], "already_this_hour": already}


if __name__ == "__main__":
    p = write_default_config()
    cfg = load_config()
    print(f"config: {p}")
    print(f"  enabled : {cfg['enabled']}")
    print(f"  key     : {'set' if cfg['api_key'] else 'NOT SET — copy from ~/clara/.env.local'}")
    print(f"  voice   : {cfg['voice_id']} (George — british, warm)")
    print(f"  triggers: {', '.join(k for k, v in cfg['triggers'].items() if v)}")
    print(f"  cap     : {cfg['lifecycle']['max_per_hour']}/hour for lifecycle, "
          f"min {cfg['lifecycle']['min_runtime_s']}s runtime")
    if len(sys.argv) > 1:
        print(json.dumps(speak(" ".join(sys.argv[1:])), indent=2))
