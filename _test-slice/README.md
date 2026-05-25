# _test-slice

A sandbox proof of the Abu Zahir per-customer session architecture. One
fabricated customer (`test-fatima`), one pending inbound, three skills,
two shared files. No real customer data, no external transport.

## Layout

```
_test-slice/
├── README.md                          (this file)
├── _shared/
│   ├── VOICE.md                       single-source voice rules + glossary
│   ├── PHRASE_BLOCKLIST.md            cross-customer repetition ledger
│   ├── sweep-state.json               poll cursor
│   └── skills/
│       ├── strategize.md              build STRATEGY.md from pending+context
│       ├── gate.md                    five pre-send checks
│       └── commit.md                  simulated send, filesystem only
└── customers/
    └── test-fatima/
        ├── CLAUDE.md                  auto-loads on session open
        ├── PROFILE.md                 name, register, signoff state
        ├── COMMITMENTS.md             three locked commitments
        ├── CHAT-LOG.md                five inbound/outbound pairs
        ├── REPORTS-LOG.md             Detection + Severance writeups
        ├── phrase-ledger.md           seeded phrasing ledger
        ├── inbox/
        │   ├── pending.md             one unanswered inbound
        │   └── archive/               commit moves cleared inbounds here
        ├── drafts/                    candidate outbounds land here
        └── reports/                   reserved for future report skill
```

## The test loop

The loop runs entirely on the local filesystem. No Etsy, no Chrome MCP,
no Telegram.

Exact commands to run the test:

```
cd /Users/tony/abu-zahir-ops/_test-slice/customers/test-fatima
claude
```

(If running inside the hsk1-flashcards sandbox, replace the cd target
with `/home/user/hsk1-flashcards/_test-slice/customers/test-fatima` or
the equivalent path in your clone.)

Then inside the Claude Code session, in order:

1. `/strategize`
   Reads pending.md, COMMITMENTS, last five chat, ledgers, voice.
   Writes `STRATEGY.md` in the current directory. Review the artifact
   before going further.

2. `/draft`
   The LLM drafts an outbound inline in chat using `STRATEGY.md` and
   `_shared/VOICE.md`. Iterate in chat as needed.

3. Save the approved draft to `drafts/pending-draft.md`.

4. `/gate`
   Runs the five checks: commitment congruency, listing scope, full
   content diff against last two reports + last five outbounds, prior
   consistency, crisis check. Plus voice spot-checks (em dash,
   calendar date, body list, multi-ask, rotation collision, length).
   Outputs `PASS` or a list of flags. Halts on any flag.

5. On `PASS`, Tony types exactly `approved` or `send it` in chat. The
   strings are case-sensitive triggers; nothing adjacent counts.

6. `/commit`
   Appends the approved text to CHAT-LOG.md, extracts any new
   commitments into COMMITMENTS.md, updates phrase-ledger.md and
   `_shared/PHRASE_BLOCKLIST.md`, archives `inbox/pending.md` into
   `inbox/archive/<timestamp>.md`, truncates pending.md. Prints one
   confirmation line.

## What this test is proving

- CLAUDE.md auto-loads the locked architecture without manual stitching.
- The session greeting reads the inbox and reports the pending count
  correctly.
- `/strategize` produces a STRATEGY.md whose fields are all populated
  with values derived from this customer's actual files, not from
  templates.
- `/gate` catches contradictions (try planting one: edit the draft to
  say "Fidelity Lock is now set" while COMMITMENTS still locks the
  current phase as Vacuum Hold; gate should flag
  `commitment-conflict:commit-002`).
- `/commit` touches all four files (CHAT-LOG, COMMITMENTS if new
  commitments introduced, phrase-ledger, PHRASE_BLOCKLIST) and
  archives pending.

## Constraints

- Do not modify anything outside `_test-slice/`.
- Do not call any external API.
- The fabricated customer is fabricated. Nothing in this slice maps to
  a real intake.
