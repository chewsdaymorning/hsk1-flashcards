---
name: strategize
description: Build the per-reply strategy artifact for the active customer session. Reads pending inbound + commitments + recent chat + phrase ledgers + voice, writes customers/<id>/STRATEGY.md. Refuses to overwrite without explicit confirmation.
---

# strategize

## When to invoke

Invoke at the top of a reply cycle, after the session has auto-loaded the
customer context, and before any drafting happens. The artifact this skill
produces is the contract that the draft step and the gate step both read
from.

## Inputs to read (in this order)

1. `inbox/pending.md` — the unanswered inbound. If empty, halt and report
   "no pending inbound, nothing to strategise."
2. `COMMITMENTS.md` — the full file. Every LOCKED entry is in scope until
   the case closes.
3. `CHAT-LOG.md` — the last five entries only. Read the tail.
4. `phrase-ledger.md` — the top fifty rows by count.
5. `../../_shared/PHRASE_BLOCKLIST.md` — the top thirty rows.
6. `../../_shared/VOICE.md` — full file.
7. `PROFILE.md` — full file. Needed for register_lock and recent_signoff.

## Output

Write to `STRATEGY.md` in the current customer directory. If
`STRATEGY.md` already exists, do NOT overwrite. Print the existing path,
print its mtime, and ask Tony to confirm overwrite with the word
"overwrite". On confirmation, replace. Otherwise stop.

## Required fields in STRATEGY.md

Use a markdown structure with each of these as a level-two heading. Every
field must be filled. No empty fields, no "TBD".

- `commitments_in_scope` — list each LOCKED COMMITMENTS entry that the
  pending message touches, by its anchor id. If a commitment is not
  touched but still constrains the reply (for example, a phase lock that
  governs the entire window), include it and mark constraint-only.
- `register` — copy verbatim from PROFILE.register_lock.
- `hard_line_flags` — flags that the gate must enforce on this reply.
  At minimum: body-symptom-requires-physician-parallel if the inbound
  mentions any body sensation; no-malefic-pivot if any line could be read
  as inviting a working against a third party; no-off-platform if any
  line could pull the conversation off Etsy.
- `phrases_to_avoid` — take the top entries from the customer phrase
  ledger and the cross-customer blocklist. Anything with count two or
  more on the customer ledger goes here. Anything on the blocklist with
  last_used_date inside the cooldown window goes here.
- `greeting_to_rotate_to` — name the greeting family. It must differ from
  the family used in the last two outbounds and must not collide with
  PROFILE.recent_signoff's family.
- `signoff_to_rotate_to` — same rules as greeting.
- `the_one_ask` — the single ask the reply ends with. If the right move
  is to land received-and-held, write `received-and-held, no ask` and
  explain in one line.
- `target_length` — word range, drawn from VOICE.md section 5. State as
  a range like `120 to 160 words`.
- `architectural_read` — two to three sentences naming what is moving in
  the customer's field right now, in lore-correct terms. This is the
  emotional and structural reading the reply will be built on.

## Refusal cases

- No pending inbound. Halt.
- Pending inbound is malefic in intent (asks for harm against a third
  party). Do not draft a strategy that satisfies the ask. Instead write
  a STRATEGY.md whose `the_one_ask` is the redirect to permitted scope
  and whose `hard_line_flags` includes malefic-pivot-detected.
- STRATEGY.md already exists and Tony has not confirmed overwrite.
