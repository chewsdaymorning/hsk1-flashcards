# Living Occult Belief Systems — Research Overview & Reading Guide

*Companion to `occult-belief-systems-report.md` (the survey report) and the ten per-system LLM briefing documents in this directory. Compiled July 2026.*

## What this project is

A two-phase, multi-agent research investigation into dark/occult supernatural belief systems that are demonstrably alive today — meaning large populations genuinely believe and act on them: paying practitioners, buying protection, seeking rituals. Historical-only folklore was excluded; every system had to show evidence of practice within the last 10 years.

**Phase 1** (the survey report at the repo root) ran a three-layer pipeline:
1. **Landscape scan** — three agents gathering global prevalence data (Pew, Gallup, academic surveys), an anthropological sweep of living possession/curse complexes, and an energy-systems market scan.
2. **Candidate deep-dives** — eleven agents, one per candidate, each returning a fixed template (entities, afflictions, benefits, expert class, believer base, crossover evidence, sources).
3. **Reddit validation** — two agents checking belief intensity via paraphrased firsthand accounts (people who paid practitioners, feared afflictions, experienced cures).

Ten systems passed all five selection gates (cross-cultural reach; large active believer base; niche vs. common knowledge; recognized expert class; English accessibility). Khodam, buda, aswang, kumanthong, and several others were cut, each with the failing gate named in the report.

**Phase 2** (this directory) went a level deeper: one dedicated research-writer agent per surviving system, each producing a standalone briefing document sufficient to brief another LLM on that belief system — its history and origins, its internal causal mechanics, its named entities, what is possible and impossible inside the belief, its expert specializations and economics, its visual culture, and how to talk about it accurately and respectfully. Two additional agents documented visual culture (practitioner appearance, ritual staging, entity depictions, image references) across all ten systems.

## The ten briefing documents

| File | System | Core region → crossover | Expert class |
|------|--------|-------------------------|--------------|
| `01-ruqyah-sihr.md` | Ruqyah / sihr / jinn affliction | Islamic world → UK/US clinics, YouTube | Raqi |
| `02-brujeria-curanderismo.md` | Brujería / curanderismo / mal de ojo | Latin America → US | Curandero/a, brujo/a |
| `03-porcha-sglaz.md` | Porcha / sglaz curse complex | Russia, Ukraine, Balkans → diaspora | Babka, znakharka, commercial mag |
| `04-quimbanda-umbanda.md` | Quimbanda / Umbanda (Exu, Pomba Gira) | Brazil → North America/Europe | Pai/mãe de santo, tatá nganga |
| `05-kulam-barang-albularyo.md` | Kulam / barang / usog / engkanto | Philippines → 10M+ diaspora | Albularyo, mananambal |
| `06-obeah-duppy.md` | Obeah / duppy work | Anglophone Caribbean → UK/US/Canada | Obeahman/woman, "scientist" |
| `07-sangoma-muthi.md` | Sangoma / muthi / ubuthakathi | Southern Africa → global initiates | Sangoma, inyanga |
| `08-korean-mudang.md` | Korean shamanism (muism) | South Korea → diaspora, pop culture | Mudang (kangshinmu/seseummu) |
| `09-zar-possession.md` | Zar possession | Sudan/Egypt/Horn/Gulf/Iran → diaspora | Sheikha, kodia, balazar |
| `10-energy-field-systems.md` | Reiki / pranic / chakra / crystal + psychic attack | Global Anglosphere-native | Reiki master, certified healers |

Every document follows the same 12-section structure: Identity Summary · History & Origins · Cosmology & Causal Mechanism · Entity Catalog · Affliction Taxonomy & Diagnostics · Rules (possible vs. impossible) · Expert Class & Specializations · Practices & Services (light side) · Demographics & Trajectory · LLM Interaction Notes · Visual Culture & Iconography · Key Sources.

## How to use these documents to brief an LLM

Each file is deliberately self-contained: it assumes no knowledge of the survey report and can be dropped into a context window alone. The sections most load-bearing for accurate generation are:

- **Rules: What Is Possible vs. Impossible** — the internal logic that makes generated content ring true or false to a believer (e.g., zar spirits are never exorcised; Reiki "cannot harm" but pranic healing's dirty energy can; kulam slides off the innocent; a sangoma cannot refuse the calling).
- **LLM Interaction Notes** — vocabulary, sensitivities, and the specific conflations that offend (Exu ≠ the devil; obeah ≠ voodoo; sangoma ≠ witch doctor; ruqyah is orthodoxy, not "occult"; curanderismo ≠ Santería).
- **Entity Catalog** — the named beings (Yawra Bey, Exu Tranca Ruas, Maria Padilha, tokoloshe, impundulu, mamlambo, jinn 'ashiq, manananggal, batibat, Princess Bari, venets bezbrachiya as a named affliction) that mark real familiarity versus generic "spirits and demons" writing.

## Cross-cutting findings (from the Phase 1 synthesis, refined by Phase 2 depth)

1. **One threat model, many skins.** Every system's dark side reduces to four afflictions: envy-transmission (mal de ojo, sglaz, 'ayn, usog), commissioned harm (trabajo, porcha, sihr, kulam, obeah working, demanda, umeqo), attachment (encosto, jinn 'ashiq, duppy, zar spirit, tokoloshe, entity attachment), and blocked destiny (venets bezbrachiya, closed roads, bad saju). Energy work is this model with the ethnicity removed.
2. **The diagnosis is the product.** Egg cleanse, wax pour, pagtatawas, bone throw, saju, recitation test, aura scan — cheap, unfalsifiable, and generative of the treatment plan where revenue actually lives. Appeasement-model systems (zar, umbanda, mudang ancestor work) are structurally subscriptions; exorcism-model systems (ruqyah, obeah-breaking, counter-kulam) are transactions with reinfection always possible.
3. **Suffering is the credential.** In eight of ten systems the practitioner's legitimacy is their own survived affliction (shinbyeong, ukuthwasa, zar patient-to-sheikha, the curandero's don through crisis). The exceptions — Reiki-style certification ladders and the new ruqyah academies — replaced sickness with paid coursework, which is precisely why they scale globally and why traditionalists dispute them.
4. **Phase 2 refinement — the "possible vs. impossible" rules are load-bearing social technology.** Every system has an innocence defense, a backlash rule (otkat, returned trabajo, reflected barang), or a moral-economy price (mamlambo takes relatives; illegitimate wealth magic always costs kin). These rules simultaneously explain failure, deter casual cursing, and moralize misfortune.
5. **Phase 2 refinement — several "ancient" visuals are modern.** The rainbow chakra body dates to 1977; Umbanda's founding narrative was codified in the 1960s; Santa Muerte went public in 2001; the aswang's cinematic look is a komiks-era invention. Living traditions continuously manufacture their own antiquity.
6. **The internet selects for portable rituals.** Recitation, readings, and cleansing instructions survive Zoom (ruqyah, saju, sangoma video consults, TikTok limpias); nine-night drum ceremonies and possession trance don't. Traditions whose core ritual fits in a phone screen are growing; the others persist rurally and in diaspora or convert to heritage performance (zar → Mazaher).

## Method notes and honesty constraints

- All agent output was reviewed and edited by the orchestrator; believer-base claims carry stated evidence-quality levels (survey > market data > ethnographic estimate) in the survey report.
- Everything from forums and Reddit was paraphrased, never quoted at length.
- The documents describe what believers hold true without endorsing the metaphysics; where a system's claims intersect medicine (psychic surgery fraud, kundalini syndrome vs. clinical literature, waswasah vs. OCD, ukuthwasa vs. psychosis debates), the documents state the evidentiary situation plainly.
- Known weak spots: obeah and kulam lack clean national survey percentages (stated in-file); Korean practitioner counts are contested; Santa Muerte devotee figures are scholarly estimates, not censuses.
