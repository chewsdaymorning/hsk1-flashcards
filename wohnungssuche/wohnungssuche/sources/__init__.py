"""Scraping-free discovery sources.

The portals block scraping, but their saved-search agents ("Suchagent")
deliver every new listing by e-mail, and a local Fredy installation
(github.com/orangecoding/fredy) already watches all portals including
ImmoScout24.  These sources read alert mails and Fredy's database instead of
crawling the portals.
"""

from wohnungssuche.sources.fredy import FredyScraper
from wohnungssuche.sources.mailbox import (
    EmailAlertScraper,
    FileMailbox,
    ImapMailbox,
    Mailbox,
)

__all__ = [
    "EmailAlertScraper",
    "FredyScraper",
    "FileMailbox",
    "ImapMailbox",
    "Mailbox",
]
