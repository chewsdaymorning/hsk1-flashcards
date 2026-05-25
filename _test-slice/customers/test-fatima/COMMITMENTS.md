# COMMITMENTS — test-fatima

LOCKED commitments survive the full case. They are read by strategize on
every reply cycle and enforced by gate. New commitments are appended by
the commit skill with a source-message anchor.

---

## commit-001 — Named Khodam assigned

- status: LOCKED
- locked_at: 2026-05-11
- source: out-001 (Detection delivery message)
- statement: "Marid al-Sabr, the Patient Marid, is assigned to your
  case and stands at the bench for the duration of this working."

The name `Marid al-Sabr` is the canonical reference. No substitution,
no shortening to `the Marid`, no anglicising to `the Patient One`
inside outbound text.

---

## commit-002 — Phase sequence locked

- status: LOCKED
- locked_at: 2026-05-18
- source: out-003 (mid-Vacuum-Hold check-in)
- statement: "Phase sequence for this case is Detection, then
  Severance, then Vacuum Hold, then Fidelity Lock. The current
  phase is Vacuum Hold."

Phase order is not reversible. Vacuum Hold runs until the field
quiets enough to seat the Lock. Strategize must not draft a reply
that speaks as if the Lock is already set, and must not pull the
client backward into a phase she has already passed.

---

## commit-003 — Watch-for: Extinction Burst

- status: LOCKED
- locked_at: 2026-05-23
- source: out-005 (last outbound, vivid-dream acknowledgement)
- statement: "Extinction Burst phenomena may surface inside the
  active window after Severance. Validated as expected, not as
  regression. Body symptoms remain a physician question and a
  field question both."

When she reports old-pattern intrusions (dreams of the ex, sharp
emotional spikes, somatic echoes), the reply frames them as the
expected shape of Vacuum Hold, not as something failing. Body
symptoms specifically still require the physician-parallel framing
per VOICE.md.
