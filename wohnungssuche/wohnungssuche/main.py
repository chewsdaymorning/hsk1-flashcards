"""Command line entry point.

    python -m wohnungssuche.main run --mock       # pipeline against fixtures
    python -m wohnungssuche.main run              # live scrape (respects robots.txt)
    python -m wohnungssuche.main queue            # what is waiting for approval
    python -m wohnungssuche.main approve <hash>   # record YOUR decision
    python -m wohnungssuche.main draft <hash>     # print an enquiry to copy yourself
    python -m wohnungssuche.main schedule --at 07:30

Nothing in this program contacts a landlord.  ``approve`` records a decision and
``draft`` prints text; sending stays a manual, human step.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from wohnungssuche.agents import Orchestrator
from wohnungssuche.config import SearchConfig
from wohnungssuche.models import ApprovalStatus
from wohnungssuche.reporting import render_enquiry
from wohnungssuche.storage import Storage

DEFAULT_DB = Path("data/wohnungen.db")
DEFAULT_REPORT_DIR = Path("reports")

LOGGER = logging.getLogger("wohnungssuche")


def build_config(args: argparse.Namespace) -> SearchConfig:
    config = SearchConfig.from_json(args.config) if args.config else SearchConfig()
    if getattr(args, "platforms", None):
        config.platforms = args.platforms
    if getattr(args, "pages", None):
        config.max_pages_per_platform = args.pages
    if getattr(args, "no_details", False):
        config.fetch_details = False
    if getattr(args, "mock", False):
        # Fixtures have no detail pages, and no network should be touched.
        config.fetch_details = False
    return config


def command_run(args: argparse.Namespace) -> int:
    config = build_config(args)
    with Storage(args.db) as storage:
        orchestrator = Orchestrator(
            config=config,
            storage=storage,
            output_dir=args.output,
            use_mock=args.mock,
        )
        result = orchestrator.run()

    flagged_hashes = {listing.unique_hash for listing in result.flagged}
    plain_non_matches = [
        listing for listing in result.non_matches
        if listing.unique_hash not in flagged_hashes
    ]
    print()
    print(f"Gefunden:      {result.total_found}")
    print(f"Passend:       {len(result.matches)}")
    print(f"Nicht passend: {len(plain_non_matches)}")
    print(f"Scam-Verdacht: {len(result.flagged)}")
    print(f"Neu:           {len(result.new_hashes)}")
    for status in result.platform_status:
        state = "ok" if status.success else "FEHLER"
        detail = f" - {status.message}" if status.message else ""
        print(f"  {status.platform:<14} {state:<7} {status.listings_found} Treffer{detail}")
    if result.errors:
        print("\nProbleme im Lauf:")
        for error in result.errors:
            print(f"  - {error}")
    if result.report_path:
        print(f"\nReport: {result.report_path}")
    print(
        f"\n{len(result.matches)} Treffer warten in der Approval-Queue "
        f"(`queue`). Es wurde nichts verschickt."
    )
    return 0


def command_queue(args: argparse.Namespace) -> int:
    status = ApprovalStatus(args.status)
    with Storage(args.db) as storage:
        entries = storage.approvals(status)
    if not entries:
        print(f"Keine Eintraege mit Status '{status.value}'.")
        return 0
    for entry, listing in entries:
        print(f"[{entry['status']}] {entry['unique_hash']}")
        print(
            f"    {listing.title}\n"
            f"    {listing.rooms:g} Zi. | {listing.area_sqm:g} m² | "
            f"{listing.warm_rent:.0f} € warm | {listing.district or listing.address}"
        )
        print(f"    {listing.url}")
    print(f"\n{len(entries)} Eintraege. Nichts davon wurde verschickt.")
    return 0


def _decide(args: argparse.Namespace, status: ApprovalStatus) -> int:
    with Storage(args.db) as storage:
        if not storage.set_approval(args.hash, status, args.note):
            print(f"Kein Queue-Eintrag mit Hash {args.hash!r}.", file=sys.stderr)
            return 1
    print(f"{args.hash} -> {status.value}")
    if status is ApprovalStatus.APPROVED:
        print("Entwurf mit `draft <hash>` erzeugen und selbst versenden.")
    return 0


def command_approve(args: argparse.Namespace) -> int:
    return _decide(args, ApprovalStatus.APPROVED)


def command_reject(args: argparse.Namespace) -> int:
    return _decide(args, ApprovalStatus.REJECTED)


def command_draft(args: argparse.Namespace) -> int:
    config = build_config(args)
    with Storage(args.db) as storage:
        listing = storage.get_listing(args.hash)
        if listing is None:
            print(f"Keine Wohnung mit Hash {args.hash!r}.", file=sys.stderr)
            return 1
        approved = {
            entry["unique_hash"] for entry, _ in storage.approvals(ApprovalStatus.APPROVED)
        }
    if args.hash not in approved and not args.force:
        print(
            "Diese Wohnung ist nicht freigegeben. Erst `approve <hash>` ausfuehren "
            "(oder --force fuer eine reine Vorschau).",
            file=sys.stderr,
        )
        return 1

    text = render_enquiry(config, listing)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Entwurf gespeichert: {args.out}")
    else:
        print(text)
    return 0


def command_history(args: argparse.Namespace) -> int:
    with Storage(args.db) as storage:
        runs = storage.recent_runs(args.limit)
    if not runs:
        print("Noch keine Laeufe aufgezeichnet.")
        return 0
    for run in runs:
        print(
            f"#{run['id']} {run['started_at'][:16]} | gefunden {run['found']:>3} | "
            f"passend {run['matches']:>3} | neu {run['new_listings']:>3} | "
            f"scam {run['scam_flagged']:>2} | {run['report_path']}"
        )
    return 0


def command_schedule(args: argparse.Namespace) -> int:
    """Run once a day at a fixed local time (cron is the better option)."""
    hour, minute = (int(part) for part in args.at.split(":"))
    print(f"Taeglicher Lauf um {hour:02d}:{minute:02d}. Beenden mit Ctrl+C.")
    print("Alternative ohne Daemon (crontab -e):")
    module_dir = Path(__file__).resolve().parent.parent
    print(
        f"  {minute} {hour} * * *  cd {module_dir} && "
        f"/usr/bin/env python3 -m wohnungssuche.main run >> reports/cron.log 2>&1"
    )
    while True:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        LOGGER.info("Naechster Lauf: %s", target.strftime("%d.%m.%Y %H:%M"))
        try:
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            print("\nBeendet.")
            return 0
        try:
            command_run(args)
        except Exception as exc:  # a bad day must not kill the daemon
            LOGGER.exception("Lauf fehlgeschlagen: %s", exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wohnungssuche",
        description="Wohnungssuche Wiesbaden - Scraper, Filter und Report.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug-Logging")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Pfad zur SQLite-Datei")
    parser.add_argument("--config", help="JSON-Datei mit Suchkriterien")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Pipeline einmal ausfuehren")
    run_parser.add_argument("--mock", action="store_true", help="Fixtures statt Netzwerk")
    run_parser.add_argument("--output", default=str(DEFAULT_REPORT_DIR), help="Report-Ordner")
    run_parser.add_argument("--platforms", nargs="+", help="z. B. is24 immowelt")
    run_parser.add_argument("--pages", type=int, help="Seiten pro Plattform")
    run_parser.add_argument(
        "--no-details", action="store_true", help="Keine Expose-Detailseiten laden"
    )
    run_parser.set_defaults(func=command_run)

    queue_parser = subparsers.add_parser("queue", help="Approval-Queue anzeigen")
    queue_parser.add_argument(
        "--status",
        default=ApprovalStatus.PENDING.value,
        choices=[status.value for status in ApprovalStatus],
    )
    queue_parser.set_defaults(func=command_queue)

    approve_parser = subparsers.add_parser("approve", help="Wohnung freigeben")
    approve_parser.add_argument("hash")
    approve_parser.add_argument("--note", default="")
    approve_parser.set_defaults(func=command_approve)

    reject_parser = subparsers.add_parser("reject", help="Wohnung ablehnen")
    reject_parser.add_argument("hash")
    reject_parser.add_argument("--note", default="")
    reject_parser.set_defaults(func=command_reject)

    draft_parser = subparsers.add_parser(
        "draft", help="Anfrage-Entwurf ausgeben (verschickt nichts)"
    )
    draft_parser.add_argument("hash")
    draft_parser.add_argument("--out", help="Entwurf in Datei schreiben")
    draft_parser.add_argument(
        "--force", action="store_true", help="Vorschau ohne Freigabe"
    )
    draft_parser.set_defaults(func=command_draft)

    history_parser = subparsers.add_parser("history", help="Letzte Laeufe")
    history_parser.add_argument("--limit", type=int, default=10)
    history_parser.set_defaults(func=command_history)

    schedule_parser = subparsers.add_parser("schedule", help="Taeglich laufen lassen")
    schedule_parser.add_argument("--at", default="07:30", help="Uhrzeit HH:MM")
    schedule_parser.add_argument("--mock", action="store_true")
    schedule_parser.add_argument("--output", default=str(DEFAULT_REPORT_DIR))
    schedule_parser.add_argument("--platforms", nargs="+")
    schedule_parser.add_argument("--pages", type=int)
    schedule_parser.add_argument("--no-details", action="store_true")
    schedule_parser.set_defaults(func=command_schedule)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
