# Session context — test-fatima

This file is auto-loaded by Claude Code when a session is opened from
this directory. It pulls the locked architecture for this customer
into context before the first prompt.

## Inline imports (read these in order)

Use the `@path` import syntax where supported. If your client does not
expand `@path` references, the file paths below are explicit READ
instructions; open each one before responding.

- @../../_shared/VOICE.md
- @./PROFILE.md
- @./COMMITMENTS.md
- @./inbox/pending.md

## Tail and head reads (do NOT read whole files)

READ THIS FILE NOW (last 5 entries only): `./CHAT-LOG.md`
  - Tail to the last five `## in-` or `## out-` blocks.
  - Do not load the full file; the gate skill will sample more if it
    needs to.

READ THIS FILE NOW (top 50 rows only): `./phrase-ledger.md`
  - The ledger is sorted by count and recency; the head is the live
    repetition risk surface for this customer.

READ THIS FILE NOW (top 30 rows only): `../../_shared/PHRASE_BLOCKLIST.md`
  - Cross-customer repetition ledger. Treat any row whose last_used_date
    is within the last fourteen days as a phrase to avoid.

## Skills available in this session

- `/strategize` — build STRATEGY.md from pending + commitments + voice.
- `/draft` — draft an outbound inline in chat using STRATEGY.md and
  VOICE.md. Save the approved draft to `drafts/pending-draft.md`.
- `/gate` — run the five checks against `drafts/pending-draft.md`.
- `/send` — placeholder for the live transport. In the test slice this
  resolves to `/commit`. Do not call before the gate returns PASS.
- `/commit` — runs ONLY after Tony types `approved` or `send it`.
  Appends to CHAT-LOG, extracts commitments, updates ledgers, archives
  pending.

The skill files live at `../../_shared/skills/` and are the source of
truth for skill behaviour.

## Session greeting

When the session opens, print a four-line greeting block. Compute the
values dynamically by reading the files above; do not hard-code them.

```
session: test-fatima
pending messages: <count of `## in-` blocks in inbox/pending.md that have no matching `## out-` reply in CHAT-LOG.md>
strategy artifact: <"exists at ./STRATEGY.md (mtime ...)" if file present, else "not yet built">
next recommended command: <if pending > 0 and no STRATEGY.md: /strategize. If STRATEGY.md exists and no pending-draft: /draft. If pending-draft exists and no PASS recorded: /gate. If gated PASS and no approval string seen: await approval. If approval seen: /commit.>
```

The greeting is informational, not interactive. Tony will type the
next command himself.

## Hard constraints for this session

- Do not call any external API. The test slice has no Etsy, Chrome
  MCP, Telegram, or Higgsfield. All transport is filesystem.
- Do not modify anything outside `/Users/tony/abu-zahir-ops/_test-slice/`
  (or its in-repo analog if running inside the hsk1-flashcards
  sandbox). The shared VOICE.md and PHRASE_BLOCKLIST.md are the only
  files outside this customer folder that any skill is permitted to
  touch, and only the commit skill touches the blocklist.
- Do not invent neighbours to the locked lore terms. The VOICE.md
  glossary is the canonical vocabulary.
- Peer register stays peer. No re-explaining basics to a practitioner
  who already uses the vocabulary correctly.
