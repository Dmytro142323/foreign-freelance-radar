#!/usr/bin/env python3
"""
Foreign Freelance Radar

One-file lead finder for project-based freelance work:
- Freelancer.com public active projects API
- PeoplePerHour public freelance project pages
- Algora bounty page
- public Telegram channel feeds via https://t.me/s/<channel>

It does NOT auto-apply, auto-message, or spam anyone. It only finds, filters,
scores, saves, and optionally sends Telegram cards to you.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


OUTPUT_JSON = Path("foreign_freelance_radar_results.json")
OUTPUT_MD = Path("foreign_freelance_radar_results.md")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 ForeignFreelanceRadar/1.0"
)


@dataclass
class Source:
    name: str
    kind: str
    enabled: bool
    url: str = ""
    query: str = ""
    channel: str = ""
    direction: str = ""


@dataclass
class Lead:
    title: str
    source: str
    url: str
    budget: str = "Not specified"
    description: str = ""
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_step: str = ""
    score: float = 0.0
    raw_source_kind: str = ""


# 25 sources/directions. Enabled defaults focus on project-feed sources,
# not full-time job boards. Telegram channels are public-feed based; edit
# channel names or enable more once you know which feeds you like.
SOURCES: list[Source] = [
    Source("Freelancer - web scraping", "freelancer", True, query="web scraping"),
    Source("Freelancer - API integrations", "freelancer", True, query="api integration"),
    Source("Freelancer - AI automation", "freelancer", True, query="ai automation"),
    Source("Freelancer - React Next.js", "freelancer", True, query="react next.js"),
    Source("Freelancer - WordPress", "freelancer", True, query="wordpress plugin"),
    Source("Freelancer - Chrome extensions", "freelancer", True, query="chrome extension"),
    Source("Freelancer - dashboards CRM", "freelancer", True, query="dashboard crm"),
    Source("Freelancer - Zapier Make n8n", "freelancer", True, query="zapier make n8n"),
    Source("PPH - Technology Programming", "peopleperhour", True, url="https://www.peopleperhour.com/freelance-jobs/technology-programming"),
    Source("PPH - Programming Coding", "peopleperhour", True, url="https://www.peopleperhour.com/freelance-jobs/technology-programming/programming-coding"),
    Source("PPH - Data Science Analysis", "peopleperhour", True, url="https://www.peopleperhour.com/freelance-jobs/technology-programming/data-science-analysis"),
    Source("PPH - Website Development", "peopleperhour", True, url="https://www.peopleperhour.com/freelance-jobs/technology-programming/website-development"),
    Source("PPH - CMS WordPress", "peopleperhour", True, url="https://www.peopleperhour.com/freelance-jobs/technology-programming/cms-development"),
    Source("Algora - Cal.com bounties", "algora", True, url="https://algora.io/org/cal/bounties"),
    Source("Algora - Trigger.dev bounties", "algora", True, url="https://algora.io/triggerdotdev/bounties"),
    Source("Algora - ZIO bounties", "algora", False, url="https://algora.io/org/ZIO/bounties"),
    Source("Telegram - Upwork WebDev Projects", "telegram", True, channel="upwork_webdev", direction="public Upwork-like web dev projects"),
    Source("Telegram - Freelance Jobs Feed", "telegram", True, channel="freelancejob", direction="public freelance project feed"),
    Source("Telegram - Remote Freelance Projects", "telegram", False, channel="remotejobss", direction="mixed remote jobs; enable only if project-heavy"),
    Source("Telegram - Python Freelance", "telegram", False, channel="python_jobs_feed", direction="mixed Python projects/jobs"),
    Source("Telegram - React Freelance", "telegram", False, channel="reactjs_jobs", direction="mixed React projects/jobs"),
    Source("Telegram - NoCode Automation", "telegram", False, channel="nocodejobs", direction="n8n/Zapier/Make-like projects"),
    Source("Direction - MVP web apps", "direction", False, direction="manual keyword direction for later source expansion"),
    Source("Direction - CRM automations", "direction", False, direction="manual keyword direction for later source expansion"),
    Source("Direction - AI tools", "direction", False, direction="manual keyword direction for later source expansion"),
    Source("Direction - dashboards", "direction", False, direction="manual keyword direction for later source expansion"),
    Source("Direction - browser extensions", "direction", False, direction="manual keyword direction for later source expansion"),
]


GOOD_KEYWORDS = {
    "web scraping": 2.4, "scraping": 2.1, "crawler": 1.8, "selenium": 1.5, "playwright": 1.7,
    "api": 1.9, "integration": 2.0, "automation": 2.0, "zapier": 2.1, "make.com": 2.1, "integromat": 1.8,
    "n8n": 2.2, "airtable": 1.4, "crm": 1.8, "hubspot": 1.5, "salesforce": 1.4,
    "dashboard": 1.8, "analytics": 1.2, "react": 1.6, "next.js": 1.7, "nextjs": 1.7,
    "wordpress": 1.5, "plugin": 1.2, "chrome extension": 2.1, "extension": 1.2,
    "ai": 1.2, "llm": 1.8, "openai": 1.8, "chatgpt": 1.6, "bot": 1.2, "mvp": 1.5,
    "python": 1.5, "node": 1.2, "javascript": 1.1, "typescript": 1.2, "scrape": 2.0,
}

TRASH_PATTERNS = [
    r"\bfull[- ]?time\b", r"\bpart[- ]?time office\b", r"\boffice\b", r"\bonsite\b",
    r"\bintern(ship)?\b", r"\btranslation\b", r"\btyping\b", r"\bcopy[- ]?paste\b",
    r"\bvoice[- ]?recording\b", r"\bcasino\b", r"\bgambling\b", r"\bscam\b",
    r"\bbuy followers\b", r"\bfake accounts?\b", r"\bonlyfans\b", r"\badult\b",
    r"\blogo design only\b", r"\bflyer design\b", r"\bcanva\b",
    r"\bbookkeeping\b", r"\bdata entry\b", r"\baccounting clerk\b",
]

RISK_PATTERNS = [
    (r"\burgent\b|\basap\b", "urgent timeline"),
    (r"\bvery low budget\b|\bcheap\b", "possibly low budget"),
    (r"\bno milestone\b|\boutside platform\b", "payment/process risk"),
    (r"\bcrypto\b|\bnft\b", "crypto/NFT context"),
    (r"\bcomplex\b|\blarge\b", "scope may be large"),
    (r"\bfix bug\b|\bbugfix\b", "may need quick diagnosis"),
]


def normalize_argv(argv: list[str]) -> list[str]:
    """Accept a few common typo-ish commands from chat."""
    out: list[str] = []
    skip_next = False
    for i, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg == "--" and i + 1 < len(argv) and argv[i + 1] in {"audit-sources", "--audit-sources"}:
            out.append("--audit-sources")
            skip_next = True
        elif arg == "--ner-source":
            out.append("--per-source")
        elif arg.startswith("--min-source") and arg != "--min-source":
            out.extend(["--min-source", arg.replace("--min-source", "", 1)])
        else:
            out.append(arg)
    return out


def fetch_url(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            charset = res.headers.get_content_charset() or "utf-8"
            return res.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        # Some public project-feed sites occasionally serve an expired/mismatched
        # chain to Python while browsers still open them. Fallback keeps source
        # auditing useful without weakening requests unless this exact error occurs.
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as res:
            charset = res.headers.get_content_charset() or "utf-8"
            return res.read().decode(charset, errors="replace")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def absolute_url(url: str, base: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(url))


def parse_budget_from_text(text: str) -> str:
    patterns = [
        r"(?:\$|USD\s*)\s?\d[\d,]*(?:\s?-\s?(?:\$|USD\s*)?\d[\d,]*)?",
        r"(?:£|GBP\s*)\s?\d[\d,]*(?:\s?-\s?(?:£|GBP\s*)?\d[\d,]*)?",
        r"(?:€|EUR\s*)\s?\d[\d,]*(?:\s?-\s?(?:€|EUR\s*)?\d[\d,]*)?",
        r"\d[\d,]*\s?(?:kr|NOK|USD|EUR|GBP)",
        r"(?:fixed price|hourly|per hour|/hr)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(0).strip()
    return "Not specified"


def freelancer_url(project: dict[str, Any]) -> str:
    seo = project.get("seo_url")
    if seo:
        return "https://www.freelancer.com/projects/" + str(seo).strip("/")
    return f"https://www.freelancer.com/projects/{project.get('id', '')}"


def fetch_freelancer(source: Source, per_source: int) -> list[Lead]:
    params = {
        "limit": str(per_source),
        "full_description": "true",
        "job_details": "true",
        "query": source.query,
    }
    url = "https://www.freelancer.com/api/projects/0.1/projects/active/?" + urllib.parse.urlencode(params)
    data = json.loads(fetch_url(url))
    projects = data.get("result", {}).get("projects", [])
    leads: list[Lead] = []
    for p in projects:
        budget = p.get("budget") or {}
        currency = p.get("currency") or {}
        sign = currency.get("sign") or currency.get("code") or "$"
        if budget.get("minimum") and budget.get("maximum"):
            budget_text = f"{sign}{budget.get('minimum')} - {sign}{budget.get('maximum')}"
        elif budget.get("minimum"):
            budget_text = f"from {sign}{budget.get('minimum')}"
        else:
            budget_text = "Not specified"
        desc = clean_text(p.get("description", ""))
        leads.append(Lead(
            title=clean_text(p.get("title", "")) or "Untitled project",
            source=source.name,
            url=freelancer_url(p),
            budget=budget_text,
            description=desc[:900],
            raw_source_kind=source.kind,
        ))
    return leads


def fetch_peopleperhour(source: Source, per_source: int) -> list[Lead]:
    page = fetch_url(source.url)
    leads: list[Lead] = []

    marker = "window.PPHReact.initialState="
    if marker in page:
        state_text = page.split(marker, 1)[1]
        state, _ = json.JSONDecoder().raw_decode(state_text)
        projects = (state.get("entities") or {}).get("projects") or {}
        for project in projects.values():
            attrs = project.get("attributes") or {}
            title = clean_text(attrs.get("title", ""))
            desc = clean_text(attrs.get("proj_desc", ""))
            if not title:
                continue
            currency = attrs.get("currency") or ""
            budget = attrs.get("budget") or attrs.get("budget_converted")
            if budget:
                budget_text = f"{currency} {budget}".strip()
            else:
                budget_text = parse_budget_from_text(f"{title} {desc}")
            leads.append(Lead(
                title=title[:180],
                source=source.name,
                url=attrs.get("url") or source.url,
                budget=budget_text or "Not specified",
                description=desc[:900],
                raw_source_kind=source.kind,
            ))
            if len(leads) >= per_source:
                return leads

    # PPH is React-rendered, but its HTML usually contains job links and adjacent text.
    link_pattern = re.compile(r'href="(?P<href>/freelance-jobs/[^"]+?)"[^>]*>(?P<title>[\s\S]{5,180}?)</a>', re.I)
    seen: set[str] = set()
    for match in link_pattern.finditer(page):
        href = html.unescape(match.group("href"))
        title = clean_text(match.group("title"))
        if not title or len(title) < 8 or title.lower() in {"technology programming", "programming coding"}:
            continue
        url = absolute_url(href, "https://www.peopleperhour.com")
        if url in seen:
            continue
        seen.add(url)
        start = max(0, match.start() - 800)
        end = min(len(page), match.end() + 1600)
        context = clean_text(page[start:end])
        leads.append(Lead(
            title=title[:180],
            source=source.name,
            url=url,
            budget=parse_budget_from_text(context),
            description=context[:900],
            raw_source_kind=source.kind,
        ))
        if len(leads) >= per_source:
            break
    return leads


def fetch_algora(source: Source, per_source: int) -> list[Lead]:
    page = fetch_url(source.url)
    leads: list[Lead] = []
    seen: set[str] = set()

    for match in re.finditer(r'href="(?P<href>https://github\.com/[^"]+/issues/\d+)"', page, flags=re.I):
        url = html.unescape(match.group("href"))
        if url in seen:
            continue
        seen.add(url)
        context = clean_text(page[max(0, match.start() - 500): min(len(page), match.end() + 900)])
        money = parse_budget_from_text(context)
        title_context = context
        money_match = re.search(r"\$[\d,]+", title_context)
        if money_match:
            title_context = title_context[money_match.start():]
        title = re.sub(r"^\$[\d,]+\s*", "", title_context).strip()
        title = re.sub(r"\s+(Open|Completed|Create new bounties).*$", "", title, flags=re.I).strip()
        leads.append(Lead(
            title=(title[:160] or "Algora bounty"),
            source=source.name,
            url=url,
            budget=money,
            description=context[:900],
            raw_source_kind=source.kind,
        ))
        if len(leads) >= per_source:
            return leads

    # Algora bounty pages contain bounty links plus dollar values in the HTML.
    for match in re.finditer(r'href="(?P<href>/(?:bounties|issues|claims|[^"]*bount[^"]*)[^"]*)"[^>]*>(?P<title>[\s\S]{3,260}?)</a>', page, flags=re.I):
        title = clean_text(match.group("title"))
        url = absolute_url(match.group("href"), "https://algora.io")
        if not title or url in seen:
            continue
        seen.add(url)
        context = clean_text(page[max(0, match.start() - 1000): min(len(page), match.end() + 1800)])
        leads.append(Lead(
            title=title[:180],
            source=source.name,
            url=url,
            budget=parse_budget_from_text(context),
            description=context[:900],
            raw_source_kind=source.kind,
        ))
        if len(leads) >= per_source:
            break

    if not leads:
        # Fallback: create cards from visible bounty-like blocks.
        for block in re.split(r"</(?:article|li|tr|div)>", page, flags=re.I):
            text = clean_text(block)
            if "$" not in text or len(text) < 30:
                continue
            leads.append(Lead(
                title=text[:120],
                source=source.name,
                url=source.url,
                budget=parse_budget_from_text(text),
                description=text[:900],
                raw_source_kind=source.kind,
            ))
            if len(leads) >= per_source:
                break
    return leads


def fetch_telegram(source: Source, per_source: int) -> list[Lead]:
    url = f"https://t.me/s/{source.channel}"
    page = fetch_url(url)
    leads: list[Lead] = []
    posts = re.split(r'<div class="tgme_widget_message_wrap', page)
    for post in posts[1:]:
        text_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)</div>', post, re.I)
        if not text_match:
            continue
        text = clean_text(text_match.group(1))
        if len(text) < 40:
            continue
        link_match = re.search(r'data-post="([^"]+)"', post)
        post_url = f"https://t.me/{link_match.group(1)}" if link_match else url
        title = text.split(". ")[0].split("\n")[0][:120]
        if len(title) < 10:
            title = "Telegram freelance project"
        leads.append(Lead(
            title=title,
            source=source.name,
            url=post_url,
            budget=parse_budget_from_text(text),
            description=text[:900],
            raw_source_kind=source.kind,
        ))
        if len(leads) >= per_source:
            break
    return leads


def is_trash(lead: Lead) -> bool:
    hay = f"{lead.title} {lead.description}".lower()
    return any(re.search(p, hay, flags=re.I) for p in TRASH_PATTERNS)


def score_and_enrich(lead: Lead) -> Lead:
    hay = f"{lead.title} {lead.description}".lower()
    reasons: list[str] = []
    score = 0.0

    for keyword, weight in GOOD_KEYWORDS.items():
        if keyword_matches(hay, keyword):
            reasons.append(keyword)
            score += weight

    if lead.budget != "Not specified":
        score += 0.7
    if lead.raw_source_kind in {"freelancer", "peopleperhour", "algora", "telegram"}:
        score += 0.6
    if re.search(r"\b(fixed|budget|milestone|deliverable|build|create|develop|integrate|automate|scrape)\b", hay):
        score += 1.1
    if re.search(r"\b\d{1,3}\s?(hours|days|week|weeks)\b", hay):
        score += 0.4

    risks: list[str] = []
    for pat, label in RISK_PATTERNS:
        if re.search(pat, hay, flags=re.I) and label not in risks:
            risks.append(label)

    if not reasons:
        reasons.append("project-feed source")
        score += 0.4
    if not risks:
        risks.append("no obvious risks")

    lead.reasons = reasons[:8]
    lead.risks = risks[:5]
    lead.score = round(score, 2)
    lead.next_step = make_next_step(lead)
    return lead


def keyword_matches(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword.lower()).replace(r"\ ", r"\s+")
    if re.fullmatch(r"[a-z0-9+#.]+", keyword.lower()):
        return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text, flags=re.I) is not None
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text, flags=re.I) is not None


def make_next_step(lead: Lead) -> str:
    hay = f"{lead.title} {lead.description}".lower()
    if "scrap" in hay or "crawler" in hay:
        return "Ask for target sites, fields, volume, anti-bot constraints, and offer a small sample scraper in 24-48 hours."
    if "api" in hay or "integration" in hay or "zapier" in hay or "n8n" in hay or "make.com" in hay:
        return "Offer a short discovery: which APIs/tools, trigger flow, data fields, and first working automation in 24-48 hours."
    if "react" in hay or "next" in hay or "dashboard" in hay:
        return "Ask for current repo/design/data source and propose one visible screen or dashboard slice as the first milestone."
    if "wordpress" in hay:
        return "Ask for wp-admin/plugin/theme access details, exact change list, and propose a safe staging-first fix."
    if "ai" in hay or "llm" in hay or "openai" in hay or "chatgpt" in hay:
        return "Clarify model/API, input data, success criteria, and propose a tiny proof-of-concept before the full build."
    return "Send a concise manual reply: confirm the goal, ask 2-3 discovery questions, and suggest the first concrete deliverable."


def dedupe(leads: Iterable[Lead]) -> list[Lead]:
    result: list[Lead] = []
    seen: set[str] = set()
    for lead in leads:
        key = (lead.url or lead.title).strip().lower()
        if key and key not in seen:
            result.append(lead)
            seen.add(key)
    return result


def collect(args: argparse.Namespace) -> tuple[list[Lead], list[dict[str, str]]]:
    all_leads: list[Lead] = []
    errors: list[dict[str, str]] = []
    enabled = [s for s in SOURCES if s.enabled and s.kind != "direction"]
    for source in enabled:
        try:
            if source.kind == "freelancer":
                leads = fetch_freelancer(source, args.per_source)
            elif source.kind == "peopleperhour":
                leads = fetch_peopleperhour(source, args.per_source)
            elif source.kind == "algora":
                leads = fetch_algora(source, args.per_source)
            elif source.kind == "telegram":
                leads = fetch_telegram(source, args.per_source)
            else:
                leads = []
            all_leads.extend(leads)
            time.sleep(args.sleep)
        except Exception as exc:  # keep the radar running even if a source breaks
            errors.append({"source": source.name, "error": f"{type(exc).__name__}: {exc}"})

    filtered = [score_and_enrich(x) for x in dedupe(all_leads) if not is_trash(x)]
    filtered = [x for x in filtered if x.score >= args.min_score]

    by_source_count: dict[str, int] = {}
    balanced: list[Lead] = []
    for lead in sorted(filtered, key=lambda x: x.score, reverse=True):
        count = by_source_count.get(lead.source, 0)
        if count >= args.max_source:
            continue
        balanced.append(lead)
        by_source_count[lead.source] = count + 1
        if len(balanced) >= args.limit:
            break

    if len(balanced) < min(args.limit, args.min_source):
        # Soft scoring: if strict balancing/min-score leaves too few cards,
        # fill from the rest instead of producing a sterile empty feed.
        existing = {x.url for x in balanced}
        for lead in sorted(filtered, key=lambda x: x.score, reverse=True):
            if lead.url not in existing:
                balanced.append(lead)
                existing.add(lead.url)
            if len(balanced) >= args.limit:
                break
    return balanced, errors


def card_text(lead: Lead, index: int) -> str:
    return (
        f"EN Freelance Deal #{index}\n\n"
        f"{lead.title}\n"
        f"Source: {lead.source}\n"
        f"Budget: {lead.budget}\n"
        f"Score: {lead.score}/10 soft\n\n"
        f"Why it looks like an order:\n"
        f"{', '.join(lead.reasons) if lead.reasons else 'project-feed source'}\n\n"
        f"Risks:\n"
        f"{', '.join(lead.risks) if lead.risks else 'no obvious risks'}\n\n"
        f"How to enter:\n"
        f"{lead.next_step}\n\n"
        f"Link: {lead.url}"
    )


def save_results(leads: list[Lead], errors: list[dict[str, str]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(leads),
        "leads": [asdict(x) for x in leads],
        "source_errors": errors,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Foreign Freelance Radar Results",
        "",
        f"Generated: {payload['generated_at']}",
        f"Leads: {len(leads)}",
        "",
    ]
    for i, lead in enumerate(leads, 1):
        lines.extend([
            f"## EN Freelance Deal #{i}: {lead.title}",
            "",
            f"- Source: {lead.source}",
            f"- Budget: {lead.budget}",
            f"- Score: {lead.score}/10 soft",
            f"- Reasons: {', '.join(lead.reasons)}",
            f"- Risks: {', '.join(lead.risks)}",
            f"- Next step: {lead.next_step}",
            f"- Link: {lead.url}",
            "",
            clean_text(lead.description)[:500],
            "",
        ])
    if errors:
        lines.extend(["## Source errors", ""])
        for err in errors:
            lines.append(f"- {err['source']}: {err['error']}")
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def send_telegram(cards: list[str]) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before sending.")
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    for card in cards:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": card[:3900],
            "disable_web_page_preview": "false",
        }).encode("utf-8")
        req = urllib.request.Request(api, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8", errors="replace")
            if '"ok":true' not in body:
                raise RuntimeError(f"Telegram send failed: {body[:300]}")
        time.sleep(0.6)


def audit_sources() -> None:
    print("Foreign Freelance Radar source audit\n")
    for i, source in enumerate(SOURCES, 1):
        state = "ENABLED " if source.enabled else "disabled"
        target = source.url or source.channel or source.query or source.direction
        print(f"{i:02d}. {state} | {source.kind:14s} | {source.name} | {target}")
    print("\nNote: public Telegram feeds can disappear or be renamed; later Telethon user-session support can reuse this source list for closed chats.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Find project-based freelance leads and send Telegram cards.")
    p.add_argument("--audit-sources", action="store_true", help="Show enabled/disabled sources and exit.")
    p.add_argument("--limit", type=int, default=20, help="Max cards to print/send.")
    p.add_argument("--per-source", "--max-per-source-fetch", type=int, default=20, help="How many raw items to fetch per source.")
    p.add_argument("--max-source", type=int, default=5, help="Max final cards from one source.")
    p.add_argument("--min-source", type=int, default=15, help="Soft target for minimum number of cards before relaxing strictness.")
    p.add_argument("--min-score", type=float, default=1.2, help="Soft relevance threshold. Lower = more leads.")
    p.add_argument("--send", action="store_true", help="Send cards to Telegram. Without this, dry-run prints to terminal.")
    p.add_argument("--dry-run", action="store_true", help="Print cards only. This is the default if --send is not used.")
    p.add_argument("--sleep", type=float, default=0.4, help="Delay between source requests.")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    args = build_parser().parse_args(argv)

    if args.audit_sources:
        audit_sources()
        return 0

    leads, errors = collect(args)
    save_results(leads, errors)

    cards = [card_text(lead, i) for i, lead in enumerate(leads, 1)]
    if not cards:
        print("No leads found after filtering. Try --min-score 0.5 or enable more sources in SOURCES.")
    for card in cards:
        print(card)
        print("\n" + "-" * 72 + "\n")

    if errors:
        print("Source errors:")
        for err in errors:
            print(f"- {err['source']}: {err['error']}")
        print()

    print(f"Saved JSON: {OUTPUT_JSON.resolve()}")
    print(f"Saved Markdown: {OUTPUT_MD.resolve()}")

    if args.send:
        send_telegram(cards)
        print(f"Sent {len(cards)} cards to Telegram.")
    else:
        print("Dry-run mode: Telegram was not used. Add --send to send cards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
