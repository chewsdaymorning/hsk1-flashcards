---
name: gate
description: Run the five pre-send checks against drafts/pending-draft.md. Outputs PASS or a list of flags. Any flag halts the send.
---

# gate

## When to invoke

Invoke after a draft has been saved to
`customers/<id>/drafts/pending-draft.md`. Do not invoke against an inline
chat draft; the gate reads from disk so that the artifact under review is
the same artifact that commit will append to CHAT-LOG.

## Inputs

- `drafts/pending-draft.md` — the candidate outbound.
- `STRATEGY.md` — the contract written by strategize.
- `COMMITMENTS.md` — full file.
- `REPORTS-LOG.md` — last two entries.
- `CHAT-LOG.md` — last five outbound entries only.
- `phrase-ledger.md` and `../../_shared/PHRASE_BLOCKLIST.md`.
- `PROFILE.md`.
- `../../_shared/VOICE.md`.

## The five checks

Run all five. Do not short-circuit on the first failure; report every flag
found in a single pass so the rewrite is one round, not five.

### 1. Commitment congruency

For each LOCKED entry in COMMITMENTS.md, check that the draft does not
contradict it. Specifically:
- Phase claims must match the current phase. If COMMITMENTS says we are
  in Vacuum Hold, the draft cannot speak as if Fidelity Lock is set.
- Named Khodam must be referenced consistently. No substitution, no
  drift in spelling.
- Watch-for indicators previously validated as expected (for example,
  Extinction Burst inside the active window) must not be re-pathologised
  in the draft as if newly alarming.

Flag: `commitment-conflict:<anchor-id>`.

### 2. Listing scope

Compare anything the draft offers or implies-offering against the
purchased listing scope captured in COMMITMENTS and the inbound's ask.
The draft may not introduce a new working, a new artifact, or a new
phase that the customer has not commissioned. Strategize's
`the_one_ask` is the boundary.

Flag: `out-of-scope-offer:<short-quote>`.

### 3. Full content diff

Run a phrase-level diff between the draft and:
- The last two REPORTS-LOG entries.
- The last five CHAT-LOG outbounds.

Any phrase of four or more words that appears in both is a flag. Lore
terms from VOICE.md glossary are exempt. The customer's name and any
proper noun are exempt. Everything else is fair game.

Flag: `repeat-phrase:"<phrase>"`.

### 4. Prior consistency

Scan the draft against the last five chat outbounds and the last two
reports for tone drift, register slip (peer to consumer or vice versa),
and any flat contradiction (for example, saying the dream pattern is
new when an earlier outbound named it as expected).

Flag: `prior-contradiction:<one-line-summary>`.

### 5. Crisis check

If the inbound or the draft references a body symptom — chest pain,
breath, vision, fainting, anything physiological — the draft must
contain a physician-parallel framing: acknowledge the body, defer to a
clinician for the body, hold the field for the field. Absence of this
framing is a flag, even if the symptom in the inbound was mild.

Also flag any line in the draft that could read as medical advice, a
diagnosis, or a directive to ignore a clinician.

Flag: `crisis-framing-missing` or `medical-advice-shaped`.

## Voice spot-checks (run alongside the five)

- Em dash present anywhere. Flag: `em-dash`.
- Calendar date present. Flag: `calendar-date`.
- Bullet or numbered list inside body. Flag: `body-list`.
- More than one ask. Flag: `multi-ask`.
- Greeting or signoff family collides with last two outbounds or
  PROFILE.recent_signoff. Flag: `rotation-collision`.
- Word count outside STRATEGY.target_length. Flag: `length-off`.

## Output

If zero flags:

```
PASS
```

Print nothing else. The shell of the test loop treats a single-token
`PASS` as the signal to await Tony's "approved" / "send it".

If one or more flags:

```
HALT
- flag-id-1: short context
- flag-id-2: short context
...
```

Do not draft a fix. Do not auto-rewrite. Tony rewrites by hand or asks
for a rewrite explicitly. The gate's job is to refuse, not to repair.
