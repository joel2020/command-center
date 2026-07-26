# Connector reality check

Probed 2026-07-25, before writing any dashboard code — per PHASES.md Phase 1:
*"call each connector tool once and inspect the actual response shape. Build parsers
around what was observed, not what was assumed."*

Every row below was called once. Nothing here is assumed.

| Source | State | How the dashboard reads it |
|---|---|---|
| **Gmail** | ✅ live — `joelcarias23@gmail.com` | `search_threads` |
| **Linear** | ✅ live — workspace `aliviosearchpartners` | `list_issues` |
| **Granola** | ✅ live — 12 meetings in last 30d | `list_meetings` → `get_meeting_transcript` |
| **Calendar** | ✅ live via AppleScript — permission already granted | `osascript` |
| **Reminders** | ✅ live via AppleScript — permission already granted | `osascript` |
| **WhatsApp** | ❌ **logged out** — 0 chats, 0 messages synced | needs your action |
| **Slack** | ❌ no MCP server connected | section omitted |
| **Notion** | ❌ no MCP server connected | section omitted |
| **`~/TASKS.md`** | ❌ does not exist | section omitted |
| **Google Drive** | ❌ requires `authenticate` | not needed for the dashboard |

No macOS Automation permissions are outstanding — Calendar and Reminders both
answered on the first call.

---

## Observed response shapes

**Gmail** — `search_threads(query, pageSize, view)`
```
threads[] { id, messages[] { id, date, sender, subject, snippet,
                             labelIds[], toRecipients[] } }
```
`labelIds` carries `UNREAD` / `INBOX` / `IMPORTANT`. Message bodies are NOT included —
`get_thread` is required for content. Triage classifies on sender + subject + snippet,
which is enough and much cheaper.

**Linear** — `list_issues(limit, orderBy)`
```
issues[] { id: "ALI-115", title, description, status, statusType,
           priority { value, name }, project, projectId, assignee,
           dueDate, completedAt, updatedAt, url, gitBranchName }
```
`statusType` is the reliable field: `completed` / `started` / `unstarted` / `backlog`.
Two projects exist: *Alivio Platform & Website* and *RLTRS — Colombia Real Estate
Data Network*. `dueDate` is populated on some issues — that's the TODAY source.

**Granola** — `list_meetings(time_range)`
```
meetings[] { id: uuid, title, date, known_participants }
```
Titles are descriptive enough to use directly. Transcript content requires a second
call per meeting, so the dashboard uses titles only and fetches transcripts on demand.

**Calendar / Reminders** — AppleScript
```
osascript → "calendar name | event summary | start date"
```
Calendars present: Work, Calendar, Company Holidays, Home, Mint, Recruiter Empire,
Scheduled Reminders, Birthdays, US Holidays, Siri Suggestions.

---

## Three findings that change the design

### 1. Your calendar is effectively empty
Across a ±60-day window there are **3 real events** (all on "Home") plus 6 US holidays.
Nothing at all in the next 7 days.

A TODAY section built around calendar blocks would render blank every morning. So TODAY
is built from what you actually have signal in: **Linear due dates, recent Granola
meetings, and the approved project list** — with calendar included but not load-bearing.

Calendar-conflict detection is still wired (CLAUDE.md requires detect-and-flag), it just
won't have much to detect.

### 2. WhatsApp is logged out, and it's your biggest blind spot
`~/Documents/rltrs-vault/rltrs Project/00 - Project Overview.md` says the vault was
reconstructed from Granola transcripts because *"WhatsApp group history was not
available."* Your own open-questions note says the $4,000 answer needs to be
**"in writing — WhatsApp is fine, it just needs to be recorded."**

The RLTRS.co group is where the money conversation lives, and right now nothing can
read it.

**To fix:** run `npm run login` in `~/whatsapp-mcp` and scan the QR code. That's yours
to do — it's a credential action (manual action #5), so I won't touch it.

### 3. Gmail is about to stop working
A Jul 25 notice from Google One says the account is out of storage quota and can no
longer send or receive. Triage against a dead mailbox is worthless, so this blocks
Phase 2 in practice even though Phase 2's code doesn't care.

Also live in the inbox: a GitHub fine-grained PAT (Replit) expiring in ~7 days, and a
pending signature request from `roman@bypasssolution.com`.
