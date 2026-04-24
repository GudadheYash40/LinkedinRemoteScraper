"""
BBA Fresher Remote Job Alert Bot
Scrapes multiple job boards and sends alerts via Telegram every 5 minutes.
Sources: LinkedIn (RapidAPI/JSearch), Internshala, Naukri, Unstop, RemoteOK, WeWorkRemotely
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
from telegram import Bot
from telegram.constants import ParseMode

# ─────────────────────────────────────────────
#  CONFIG — edit these or set as env variables
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID_HERE")
RAPIDAPI_KEY       = os.getenv("RAPIDAPI_KEY",        "YOUR_RAPIDAPI_KEY_HERE")

POLL_INTERVAL_SECONDS = 300   # 5 minutes
SEEN_JOBS_FILE        = Path("seen_jobs.json")

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("job_bot.log")],
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  SEEN JOBS — deduplication
# ─────────────────────────────────────────────
def load_seen() -> set:
    if SEEN_JOBS_FILE.exists():
        return set(json.loads(SEEN_JOBS_FILE.read_text()))
    return set()

def save_seen(seen: set):
    trimmed = list(seen)[-5000:]
    SEEN_JOBS_FILE.write_text(json.dumps(trimmed))

def job_id(job: dict) -> str:
    key = f"{job.get('title','')}{job.get('company','')}{job.get('url','')}"
    return hashlib.md5(key.encode()).hexdigest()

# ─────────────────────────────────────────────
#  BBA / FRESHER KEYWORD FILTER
# ─────────────────────────────────────────────
BBA_KEYWORDS = [
    "bba", "business administration", "commerce", "b.com", "bcom",
    "mba", "management", "finance", "accounting", "marketing",
    "sales", "hr", "human resource", "operations", "supply chain",
    "logistics", "business analyst", "data analyst", "excel",
    "fresher", "fresh graduate", "entry level", "0 experience",
    "0-1 year", "graduate trainee", "management trainee",
    "business development", "customer success", "account manager",
    "virtual assistant", "coordinator", "associate", "analyst",
]

EXCLUDE_KEYWORDS = ["10+ years", "5+ years", "7+ years", "8+ years", "senior director", "vp of", "vice president"]

def is_relevant(job: dict) -> bool:
    text = f"{job.get('title','')} {job.get('description','')}".lower()
    if any(ex in text for ex in EXCLUDE_KEYWORDS):
        return False
    return any(kw in text for kw in BBA_KEYWORDS)

# ─────────────────────────────────────────────
#  SOURCE 1 — LinkedIn/Indeed via JSearch (RapidAPI)
#  Free: 200 req/month | rapidapi.com search "jsearch"
# ─────────────────────────────────────────────
async def fetch_jsearch(client: httpx.AsyncClient) -> list:
    if RAPIDAPI_KEY == "YOUR_RAPIDAPI_KEY_HERE":
        log.warning("RapidAPI key not set — skipping JSearch (LinkedIn/Indeed)")
        return []
    queries = [
        "BBA fresher remote",
        "business administration entry level remote",
        "management trainee work from home",
        "fresher analyst remote India",
        "commerce graduate remote job",
    ]
    jobs = []
    for q in queries:
        try:
            resp = await client.get(
                "https://jsearch.p.rapidapi.com/search",
                params={"query": q, "num_pages": "3", "date_posted": "today", "remote_jobs_only": "true"},
                headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
                timeout=15,
            )
            for j in resp.json().get("data", []):
                jobs.append({
                    "title":       j.get("job_title", ""),
                    "company":     j.get("employer_name", ""),
                    "location":    j.get("job_city") or "Remote",
                    "url":         j.get("job_apply_link") or j.get("job_google_link", ""),
                    "description": (j.get("job_description") or "")[:400],
                    "source":      "LinkedIn/Indeed",
                    "salary":      str(j.get("job_min_salary") or ""),
                })
        except Exception as e:
            log.error(f"JSearch '{q}': {e}")
        await asyncio.sleep(1)
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 2 — Internshala
# ─────────────────────────────────────────────
async def fetch_internshala(client: httpx.AsyncClient) -> list:
    jobs = []
    urls = [
        "https://internshala.com/jobs/freshers-jobs/work-from-home/",
        "https://internshala.com/jobs/bba-jobs/work-from-home/",
        "https://internshala.com/jobs/business-development-jobs/work-from-home/",
        "https://internshala.com/jobs/marketing-jobs/work-from-home/",
        "https://internshala.com/jobs/finance-jobs/work-from-home/",
        "https://internshala.com/jobs/human-resources-jobs/work-from-home/",
        "https://internshala.com/jobs/operations-jobs/work-from-home/",
        "https://internshala.com/jobs/sales-jobs/work-from-home/",
    ]
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}
    for url in urls:
        try:
            resp = await client.get(url, headers=hdrs, timeout=15, follow_redirects=True)
            html = resp.text
            titles    = re.findall(r'class="job-title[^"]*"[^>]*>\s*(?:<[^>]+>)*([^<]+)', html)
            companies = re.findall(r'class="company-name"[^>]*>\s*(?:<[^>]+>)*([^<]+)', html)
            links     = re.findall(r'href="(/jobs/details/[^"]+)"', html)
            salaries  = re.findall(r'class="salary[^"]*"[^>]*>\s*(?:<[^>]+>)*([^<]+)', html)
            for i, title in enumerate(titles):
                jobs.append({
                    "title":       title.strip(),
                    "company":     companies[i].strip() if i < len(companies) else "Company",
                    "location":    "Remote / Work from Home",
                    "url":         f"https://internshala.com{links[i]}" if i < len(links) else url,
                    "description": "fresher bba business entry level remote work from home",
                    "source":      "Internshala",
                    "salary":      salaries[i].strip() if i < len(salaries) else "",
                })
        except Exception as e:
            log.error(f"Internshala ({url}): {e}")
        await asyncio.sleep(0.5)
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 3 — Naukri
# ─────────────────────────────────────────────
async def fetch_naukri(client: httpx.AsyncClient) -> list:
    jobs = []
    queries = [
        "bba+fresher+work+from+home",
        "business+administration+remote+fresher",
        "commerce+graduate+work+from+home",
        "management+trainee+remote",
        "fresher+finance+remote",
        "fresher+marketing+remote",
        "fresher+hr+work+from+home",
    ]
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "systemcountrycode": "IN",
        "appid": "109",
        "clientid": "d3skt0p",
        "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
    }
    for kw in queries:
        try:
            resp = await client.get(
                f"https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword"
                f"&searchType=adv&keyword={kw}&experience=0%2C1&jobAge=1&wfhType=3",
                headers=hdrs, timeout=15,
            )
            for j in resp.json().get("jobDetails", []):
                jobs.append({
                    "title":       j.get("title", ""),
                    "company":     j.get("companyName", ""),
                    "location":    "Remote / WFH",
                    "url":         j.get("jdURL", "https://naukri.com"),
                    "description": (j.get("jobDescription") or "")[:300],
                    "source":      "Naukri",
                    "salary":      j.get("salary", ""),
                })
        except Exception as e:
            log.error(f"Naukri '{kw}': {e}")
        await asyncio.sleep(1)
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 4 — Unstop
# ─────────────────────────────────────────────
async def fetch_unstop(client: httpx.AsyncClient) -> list:
    jobs = []
    try:
        resp = await client.get(
            "https://unstop.com/api/public/opportunity/search-result",
            params={"opportunity": "jobs", "per_page": "30",
                    "filters[work_exp][]": "fresher", "filters[work_type][]": "work_from_home", "sort": "recent"},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=15,
        )
        for j in resp.json().get("data", {}).get("data", []):
            jobs.append({
                "title":       j.get("title", ""),
                "company":     j.get("organisation", {}).get("name", ""),
                "location":    "Remote",
                "url":         f"https://unstop.com/{j.get('public_url','')}",
                "description": (j.get("description") or "")[:300],
                "source":      "Unstop",
                "salary":      j.get("incentives", ""),
            })
    except Exception as e:
        log.error(f"Unstop: {e}")
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 5 — RemoteOK
# ─────────────────────────────────────────────
async def fetch_remoteok(client: httpx.AsyncClient) -> list:
    jobs = []
    tags = ["business", "finance", "marketing", "sales", "operations", "management"]
    for tag in tags:
        try:
            resp = await client.get(
                f"https://remoteok.com/api?tag={tag}",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=15,
            )
            data = resp.json()
            for j in data[1:11]:
                if isinstance(j, dict):
                    jobs.append({
                        "title":       j.get("position", ""),
                        "company":     j.get("company", ""),
                        "location":    "Remote (Worldwide)",
                        "url":         j.get("url", ""),
                        "description": (j.get("description") or "")[:300],
                        "source":      "RemoteOK",
                        "salary":      j.get("salary", ""),
                    })
        except Exception as e:
            log.error(f"RemoteOK '{tag}': {e}")
        await asyncio.sleep(0.5)
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 6 — WeWorkRemotely RSS
# ─────────────────────────────────────────────
async def fetch_wwr(client: httpx.AsyncClient) -> list:
    jobs = []
    feeds = [
        "https://weworkremotely.com/categories/remote-business-exec-management-jobs.rss",
        "https://weworkremotely.com/categories/remote-finance-legal-jobs.rss",
        "https://weworkremotely.com/categories/remote-sales-and-marketing-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
    ]
    for feed in feeds:
        try:
            resp = await client.get(feed, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            for item in re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)[:10]:
                t = re.search(r'<title><!\[CDATA\[(.*?)\]\]>', item)
                l = re.search(r'<link>(.*?)</link>', item)
                c = re.search(r'<author>(.*?)</author>', item)
                if t and l:
                    jobs.append({
                        "title":       t.group(1).strip(),
                        "company":     c.group(1).strip() if c else "Unknown",
                        "location":    "Remote (Worldwide)",
                        "url":         l.group(1).strip(),
                        "description": "remote business management finance sales marketing",
                        "source":      "WeWorkRemotely",
                        "salary":      "",
                    })
        except Exception as e:
            log.error(f"WWR: {e}")
    return jobs

# ─────────────────────────────────────────────
#  SOURCE 7 — Indeed India (public search)
# ─────────────────────────────────────────────
async def fetch_indeed(client: httpx.AsyncClient) -> list:
    jobs = []
    searches = [
        ("bba fresher", "work+from+home"),
        ("management trainee", "work+from+home"),
        ("business analyst fresher", "work+from+home"),
        ("finance fresher", "work+from+home"),
    ]
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for q, loc in searches:
        try:
            resp = await client.get(
                f"https://in.indeed.com/jobs?q={q.replace(' ','+')}&l={loc}&fromage=1&limit=20",
                headers=hdrs, timeout=15, follow_redirects=True,
            )
            html = resp.text
            titles   = re.findall(r'data-testid="job-title"[^>]*>\s*(?:<[^>]+>)*([^<]+)', html)
            companies = re.findall(r'data-testid="company-name"[^>]*>\s*(?:<[^>]+>)*([^<]+)', html)
            jids     = re.findall(r'data-jk="([a-f0-9]+)"', html)
            for i, title in enumerate(titles):
                jid = jids[i] if i < len(jids) else ""
                jobs.append({
                    "title":       title.strip(),
                    "company":     companies[i].strip() if i < len(companies) else "Company",
                    "location":    "Remote / WFH",
                    "url":         f"https://in.indeed.com/viewjob?jk={jid}" if jid else "https://in.indeed.com",
                    "description": f"fresher bba business {q} remote work from home",
                    "source":      "Indeed India",
                    "salary":      "",
                })
        except Exception as e:
            log.error(f"Indeed '{q}': {e}")
        await asyncio.sleep(1)
    return jobs

# ─────────────────────────────────────────────
#  TELEGRAM HELPERS
# ─────────────────────────────────────────────
def esc(text: str) -> str:
    """Escape MarkdownV2 special chars"""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = str(text).replace(ch, f'\\{ch}')
    return text

def format_job(job: dict) -> str:
    salary = f"\n💰 *Salary:* {esc(job['salary'])}" if str(job.get("salary","")).strip() else ""
    return (
        f"🆕 *{esc(job['title'])}*\n"
        f"🏢 {esc(job['company'])}\n"
        f"📍 {esc(job['location'])}"
        f"{salary}\n"
        f"🌐 _Source: {esc(job['source'])}_\n"
        f"🔗 [Apply Here]({job['url']})\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %I:%M %p IST')}"
    )

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
async def run():
    bot  = Bot(token=TELEGRAM_BOT_TOKEN)
    seen = load_seen()
    log.info("Bot started!")

    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=(
                "✅ *BBA Fresher Remote Job Bot is LIVE\\!*\n\n"
                "🔍 *Monitoring every 5 minutes:*\n"
                "• LinkedIn \\+ Indeed \\(JSearch\\)\n"
                "• Internshala\n"
                "• Naukri\n"
                "• Unstop\n"
                "• RemoteOK\n"
                "• WeWorkRemotely\n"
                "• Indeed India\n\n"
                "🎯 Filtered for: *BBA / Fresher / Remote* jobs\n"
                "You'll get notified the moment a new job is found\\! 🚀"
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as e:
        log.error(f"Startup message failed: {e}")
        log.error("Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID!")
        return

    cycle = 0
    while True:
        cycle += 1
        log.info(f"=== Cycle {cycle} — fetching all sources ===")

        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                fetch_jsearch(client),
                fetch_internshala(client),
                fetch_naukri(client),
                fetch_unstop(client),
                fetch_remoteok(client),
                fetch_wwr(client),
                fetch_indeed(client),
                return_exceptions=True,
            )

        all_jobs = []
        source_counts = {}
        for r in results:
            if isinstance(r, list):
                for j in r:
                    source_counts[j.get("source","?")] = source_counts.get(j.get("source","?"), 0) + 1
                all_jobs.extend(r)

        log.info(f"Raw: {len(all_jobs)} | By source: {source_counts}")

        new_jobs = []
        for job in all_jobs:
            jid = job_id(job)
            if jid not in seen and is_relevant(job) and job.get("title","").strip() and job.get("url","").strip():
                new_jobs.append(job)
                seen.add(jid)

        log.info(f"New relevant jobs: {len(new_jobs)}")
        save_seen(seen)

        if new_jobs:
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"📢 *{len(new_jobs)} New BBA Fresher Remote Jobs Found\\!*\n_Cycle {cycle}_",
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception as e:
                log.error(f"Header send error: {e}")

            for job in new_jobs[:25]:  # max 25/cycle to avoid Telegram spam limits
                try:
                    await bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=format_job(job),
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(0.8)
                except Exception as e:
                    log.error(f"Send error '{job.get('title')}': {e}")
        else:
            log.info("No new jobs this cycle.")

        log.info(f"Sleeping {POLL_INTERVAL_SECONDS}s...\n")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
