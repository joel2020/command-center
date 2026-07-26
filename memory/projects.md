# Projects

<!-- The approved project list. This is the ONLY source for the dashboard's
     PROJECTS section — nothing appears there that isn't here.
     New projects enter by Joel's explicit approval, never by inference. -->

Approved 2026-07-26 from PROJECT_LIST_PROPOSAL.md, with Joel's corrections:
job search → Dormant; the two Alivio site repos folded into Alivio Search Partners;
Bravo Mechanical stays Active; tooling (whatsapp-mcp, Command Center) kept as cards;
`~/stable-lights-creations` identified as the itslitneon storefront and merged into
that project.

## Active
<!-- Format:
### <name>
- status:
- next action:
- blocked by:
- last movement:
-->

### RLTRS — Colombia real estate suite
- status: Colombia real-estate monorepo (Next.js + Supabase + Turborepo), four platforms — RLTRS, Casafy, ElMedellín, MedIsm. Phase 2 program #25–#38 fully merged 2026-07-12; studio frontend live; migrations through 0017; zero open PRs. Payment basis resolved: the Jul 16 meeting transcript confirms $4,000 plus $500 every Friday until completion, so the PDF payment schedule is safe to send.
- next action: close out ALI-28 (due 2026-07-08, 18 days overdue, $4,000 paid + $6,000) and ALI-32 (due 2026-07-15, 11 days overdue, $2,000) — both still unstarted with money attached; get Jason's written decisions per ALI-94; follow up around 2026-07-30 per the Jul 16 meeting
- blocked by: nothing
- last movement: 2026-07-25

### Alivio Search Partners
- status: master build shipped to prod 2026-07-20 (PR #118, CI green, crons fixed via Vault RPC). Marketing site and intake backend live as of 2026-07-22. The Azure deployment-name mismatch is fixed and the AI layer is live (ALI-120, Done). Covers ~/alivio-platform, ~/alivio-search-partners (aliviosearchpartners.com), and ~/orchids-aliviosearch-com (aliviosearch.com).
- next action: finish ALI-125 — compliance follow-ups: DSR workflow, subprocessor list, call-recording. It is the only issue In Progress in the workspace.
- blocked by: nothing
- last movement: 2026-07-22

### Alivio Supabase consolidation
- status: migration done and verified — 97 job postings and 4 BDR applicants moved into Alivio-OS. One extra project still live pending cutover, costing about $53.61/mo.
- next action: cut aliviosearch.com forms over to Alivio-OS, then delete the two extra Supabase projects — deletion is manual action #2 and the keeper (Alivio-OS) is one hyphen from the one to delete (Alivio)
- blocked by: nothing
- last movement: 2026-07-17

### Clara — English pronunciation app
- status: live at clara-joel-carias-projects.vercel.app. Multi-user auth and RLS verified, full A0–C2 curriculum shipped. Students: Mariana, Valentina.
- next action: work the open items in ~/clara/HANDOFF.md
- blocked by: nothing
- last movement: 2026-07-23

### Command Center
- status: Phases 0–4 built, 172 tests passing. Project list approved 2026-07-26; the Phase 4 taxonomy is still gated.
- next action: review PROPOSED_STRUCTURE.md and approve or correct the taxonomy, then install scheduler/install.sh so the four scheduled runs actually fire
- blocked by: Joel — taxonomy approval
- last movement: 2026-07-26

### itslitneon
- status: custom neon clocks client. Storefront (~/stable-lights-creations, TanStack Start on Vercel) is live but PRODUCTION CHECKOUT IS BROKEN — Stripe and Supabase env secrets are missing. Ad-creative toolkit (~/itslitneon) works, generating Reels video and ad copy through the Higgsfield MCP.
- next action: add the missing Stripe and Supabase env secrets in Vercel to restore checkout, then review the 2 branches awaiting approval
- blocked by: nothing
- last movement: 2026-07-24

### Bravo Mechanical — website + CRM
- status: HVAC CRM on Supabase project tzczkcvavudoyuuetwcr; DB fixes applied 2026-06-19. Website audit delivered 2026-07-14 (mobile LCP 14.8s, 3 leads ever); fixes not shipped. ~/bravo-verify is the only repo with a dirty tree — uncommitted work on branch fix/single-phone-number, not main.
- next action: the 1.9MB logo/favicon fix — one hour, highest-ROI item in the audit; then commit or discard the stranded fix/single-phone-number branch
- blocked by: unclear whether the client approved the audit work
- last movement: 2026-07-14

### whatsapp-mcp
- status: MCP server linked to Joel's personal WhatsApp. Currently LOGGED OUT, so nothing can read the RLTRS.co group.
- next action: cd ~/whatsapp-mcp && npm run login, then scan the QR
- blocked by: Joel — credential action, manual action #5
- last movement: 2026-07-25

## Dormant

### Job search
- status: Dormant per Joel 2026-07-26. Evidence exists (~/Desktop/Candidate Opportunity Wish List - Joel Carias.docx, ~/Documents/Resumes, heavy Indeed/LinkedIn alert volume) but it is not active work. Job alerts triage as NOISE.
- next action: none
- blocked by: nothing
- last movement: 2026-07-13

### Elite Funding Solutions
- status: production MCA CRM. No commits in about six weeks; the last one was a bugfix.
- next action: none
- blocked by: nothing
- last movement: 2026-07-14

### clara-agency
- status: superseded by ~/clara — same product, older shape.
- next action: none
- blocked by: nothing
- last movement: 2026-07-02

### elite-funding-ad
- status: Flow (Veo) + ElevenLabs + ffmpeg promo-video pipeline. Output .mp4 exists; the work looks finished.
- next action: none
- blocked by: nothing
- last movement: 2026-06-18

### MCP tooling experiments
- status: bedrock-video-mcp, elevenlabs-mcp-server, connect-apps-plugin. No recent activity.
- next action: none
- blocked by: nothing
- last movement: 2026-06-29

## Done
