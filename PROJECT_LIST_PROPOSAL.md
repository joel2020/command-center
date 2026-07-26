# Proposed project list — Phase 0

Recon date: 2026-07-25. Read-only. Nothing was moved, changed, or sent.

**Sources:** top-level `~` directories, git last-commit dates, `package.json` and
README contents, `~/Documents/rltrs-vault`, Linear workspace `aliviosearchpartners`,
and the connected Gmail inbox (`joelcarias23@gmail.com`, last 14 days).

Correct this list. The corrected version goes into `memory/projects.md` and becomes
the only thing the dashboard's PROJECTS section will ever show.

---

## Proposed ACTIVE (9)

### 1. RLTRS — Colombia real estate suite
- **status:** active client build, four platforms (RLTRS, Casafy, ElMedellín, MedIsm)
- **next action:** get Steve to state in writing what the $4,000 is for
- **blocked by:** Steve — the payment basis is unanswered
- **last movement:** 2026-07-25 (vault updated)
- **evidence:** `~/Documents/rltrs-vault/rltrs Project/` — 14 notes, frontmatter says
  `status: active`, `deal-value: 29000`, client Jason, intermediary Steve.
  Linear project *RLTRS — Colombia Real Estate Data Network*, 15+ issues.
  `~/Desktop/260716-RLTRSRevisedPaymentSchedule.pdf` (Jul 16).
- ⚠️ **ALI-32 "Week 2 — Trust layer, monetization, scraper ($2,000)" was due 2026-07-15
  and is still `Todo` — 10 days overdue, with $2,000 attached.**
- ⚠️ Money unresolved: Steve has taken $4,910 of the $10,000 Jason paid, vs $2,090 cash
  to you. Whether it offsets the $10,000 invoice is an open question in your own notes.

### 2. Alivio Search Partners — platform & website
- **status:** shipping steadily; marketing site + intake backend live as of Jul 22
- **next action:** finish ALI-125 (compliance follow-ups — DSR workflow, subprocessors)
- **blocked by:** nothing
- **last movement:** 2026-07-22
- **evidence:** `~/alivio-platform`, last commit Jul 22 (PR #126 merged, clean tree).
  Linear project *Alivio Platform & Website*. ALI-125 is the only issue `In Progress`.

### 3. Alivio Supabase consolidation
- **status:** migration done and verified; one project still live pending cutover
- **next action:** cut `aliviosearch.com` forms over, then delete the two extra projects
- **blocked by:** nothing technical — just the cutover
- **last movement:** 2026-07-17
- **evidence:** `~/alivio-consolidation/HANDOFF.md`. 97 job postings + 4 BDR applicants
  already migrated into Alivio-OS.
- 💰 **Costs ~$53.61/mo until the extra projects are deleted.** Pro plan can't pause;
  deletion is the only way to stop the charge. Deletion is manual action #2 — I will
  never do it without you saying so, and the keeper (`Alivio-OS`) is one hyphen away
  from the one to delete (`Alivio`).

### 4. Clara — English pronunciation app
- **status:** live, multi-user auth + RLS verified, full A0–C2 curriculum shipped
- **next action:** open items listed in `~/clara/HANDOFF.md`
- **blocked by:** nothing
- **last movement:** 2026-07-23
- **evidence:** `~/clara`, commit Jul 23. Live at clara-joel-carias-projects.vercel.app.
  Students named in the handoff: Mariana, Valentina.

### 5. Command Center
- **status:** Phase 0 recon (this)
- **next action:** your sign-off on this list, then build the dashboard
- **blocked by:** you
- **last movement:** 2026-07-25
- **evidence:** `~/command-center`, this repo.

### 6. itslitneon — AI ad creative toolkit
- **status:** working toolkit, generates Reels video + ad copy via Veo/Gemini
- **next action:** unknown — tell me
- **blocked by:** unknown
- **last movement:** 2026-07-22
- **evidence:** `~/itslitneon`, `package.json` describes it as the ad-creative toolkit
  for itslitneon.com. 41 files touched in the last 90 days.

### 7. stable-lights-creations
- **status:** unknown — active commits, no README
- **next action:** unknown — tell me what this is
- **blocked by:** unknown
- **last movement:** 2026-07-24 ("Add npm lockfile for reproducible installs")
- **evidence:** `~/stable-lights-creations`, TanStack Start app, 917M, clean tree.
- ❓ Second-most-recent commit of any repo you own, and I can't tell what it does.

### 8. whatsapp-mcp
- **status:** working MCP server, connected to this session right now
- **next action:** unknown — tooling, may not belong on a project list
- **blocked by:** nothing
- **last movement:** 2026-07-25
- **evidence:** `~/whatsapp-mcp`, running and linked to your personal WhatsApp.

### 9. Bravo Mechanical — website + CRM
- **status:** audit delivered Jul 14; fixes not obviously shipped
- **next action:** the 1.9MB logo/favicon fix — one hour, highest ROI item in your audit
- **blocked by:** unclear whether the client approved the work
- **last movement:** 2026-07-14
- **evidence:** `~/bravo-website-audit/AUDIT.md` (mobile LCP 14.8s, 3 leads ever).
  `~/bravo-verify` — **uncommitted changes, on branch `fix/single-phone-number`, not main.**
- ⚠️ The only repo you own with a dirty working tree. Something was left mid-fix.

---

## Proposed DORMANT (4)

| Project | Last movement | Why I think it's dormant |
|---|---|---|
| Elite Funding Solutions | 2026-07-14 | Production CRM, but no commits in 6 weeks and the last one was a bugfix |
| clara-agency | 2026-07-02 | Superseded by `~/clara` — same product, older shape |
| elite-funding-ad | 2026-06-18 | Ad render assets; output `.mp4` exists, work looks finished |
| bedrock-video-mcp / elevenlabs-mcp-server / connect-apps-plugin | 2026-06-18–29 | Tooling experiments, no recent activity |

---

## Not proposed — tell me if I'm wrong

- **`~/alivio-search-partners` and `~/orchids-aliviosearch-com`** — both Next.js, both
  last touched Jul 17. I've folded these under *Alivio Search Partners* rather than
  listing them separately. If they're independently tracked work, say so.
- **A job search.** `~/Desktop/Candidate Opportunity Wish List - Joel Carias.docx`
  (Jul 13), a `~/Documents/Resumes` folder, and a large volume of Indeed/LinkedIn
  job alerts in the inbox. This could be an active project or could be noise you
  ignore — I won't guess, and it changes email triage significantly either way.
- **File reorganization.** `~/migration-logs` and `~/Documents/Mac Safe Organization
  Logs` show a reorg ran on 2026-07-25, hours before this session. Phase 4 needs to
  know what that did before it proposes anything.

---

## Two things worth knowing now

1. **The connected Gmail is `joelcarias23@gmail.com`, not `alivio.studio.ops@gmail.com`.**
   Triage will read the personal account. Confirm that's what you want before Phase 2.

2. **That account is out of Google storage quota** — a Jul 25 notice says you can no
   longer send or receive on Gmail. Also in the last 14 days: a GitHub personal access
   token (Replit) expires in 7 days, and there's a pending signature request from
   `roman@bypasssolution.com`. Of ~30 recent inbox threads, roughly 28 were newsletters,
   job alerts, or notifications — the ACT/NOISE ratio is going to be very lopsided,
   which is good news for triage.
