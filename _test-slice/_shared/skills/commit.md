---
name: commit
description: Simulate sending an approved draft. Pure filesystem - no Etsy, no Chrome, no Telegram. Appends to CHAT-LOG, extracts new commitments, updates phrase ledgers, archives pending. Runs ONLY after Tony types "approved" or "send it".
---

# commit

## Authorisation gate

This skill runs ONLY after Tony has typed exactly `approved` or `send it`
in the chat for the current draft, in the same session, after a `PASS`
from the gate skill. If either condition is missing, refuse with one
line: `commit-unauthorised: need PASS + approval`.

Never infer approval from "ok", "looks good", "ship it" or anything
adjacent. The two strings are the only triggers. This is deliberate.

## What commit does

Five filesystem operations, in this exact order. If any operation fails,
roll back the previous ones and report which step failed. No partial
state.

### 1. Append to CHAT-LOG.md

Append a new entry to `CHAT-LOG.md` with:
- timestamp in local time, ISO format.
- `direction: outbound`.
- the full text of `drafts/pending-draft.md` as the body.
- a short anchor id like `out-NNN` where NNN is the next integer in
  sequence after the last outbound in the file.

### 2. Extract new commitments

Scan the outbound text for new commitments. A commitment is any sentence
that:
- names a new Khodam being assigned.
- locks a phase or a phase sequence.
- promises a future artifact (report, lock, reseating).
- defines a new watch-for indicator.

For each new commitment, append a LOCKED entry to `COMMITMENTS.md` with
timestamp, source-message reference (`out-NNN` from step 1), and the
verbatim sentence. If no new commitments are introduced, log one line
in the commit's stdout: `commitments: none introduced`.

Do not silently rewrite existing commitments. If the outbound restates
an existing commitment, leave COMMITMENTS untouched.

### 3. Update customer phrase-ledger.md

Tokenise the outbound text into four-word-or-longer phrase candidates
(skipping greeting line and signoff line). For each candidate:
- if it already exists in `phrase-ledger.md`, increment its count and
  update last_used.
- if it does not exist, append a new row with count one and last_used
  set to today's date.

Lore terms from VOICE.md glossary are not tracked here; the ledger is
for general phrasing, not vocabulary.

### 4. Update _shared/PHRASE_BLOCKLIST.md

Mirror the customer-ledger update against the cross-customer
PHRASE_BLOCKLIST. For each new or incremented phrase:
- write a row with phrase, last_used_customer set to the current
  customer id, count, last_used_date.
- if the row exists, increment count and update both last_used fields.

Re-sort the table by count descending before writing.

### 5. Clear inbox/pending.md and archive

Move the contents of `inbox/pending.md` to
`inbox/archive/<timestamp>.md`, where `<timestamp>` is ISO local time
with colons replaced by hyphens. Truncate `inbox/pending.md` so the
next sweep cycle starts clean. Do not delete `pending.md` itself; the
session-greeting block reads its line count to decide whether there is
a pending inbound.

## Output

One line on stdout, exact format:

```
committed: out-NNN (commitments_added=K, phrases_touched=M, archived=<archive-filename>)
```

Nothing else. No summary paragraph, no "great work" closer. The next
sweep is what comes after.

## What commit does NOT do

- Does not call any external API. No Etsy, no Chrome MCP, no Telegram,
  no email, no SMS.
- Does not edit `drafts/pending-draft.md`. That file is left on disk
  as the source of truth for what was sent; the next reply cycle
  overwrites it.
- Does not touch REPORTS-LOG.md. Reports are written by the report
  skill, not by commit. A chat reply, even one that references a
  report, is chat.
- Does not modify VOICE.md, sweep-state.json, or PROFILE.md.
