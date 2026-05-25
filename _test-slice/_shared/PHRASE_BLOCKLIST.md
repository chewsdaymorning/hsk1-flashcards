# PHRASE_BLOCKLIST.md — Cross-Customer Repetition Ledger

This table is the cross-customer repetition ledger. It is read by the
strategize skill (to seed phrases_to_avoid) and written by the commit skill
(to record phrases that have just gone out in an approved send). Sorting is
maintained roughly by `count` descending; new entries append to the bottom
and are re-sorted on the next commit pass.

A phrase landing here does not mean it is forbidden forever. It means it
has been used recently enough that re-using it inside the cooldown window
would read as a template rather than as a fresh hearing. The strategize
skill is allowed to release a phrase if its last_used_date is older than
the customer's session cadence by at least two full sends.

| phrase | last_used_customer | count | last_used_date |
|--------|--------------------|-------|----------------|
