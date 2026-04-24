# 🤖 BBA Fresher Remote Job Alert Bot

Sends new remote job alerts to your Telegram every **5 minutes** from 7 sources.

## Sources Monitored
| Source | Type | BBA Friendly |
|--------|------|-------------|
| LinkedIn + Indeed (JSearch) | API | ✅ |
| Internshala | Scrape | ✅ Best for freshers |
| Naukri | API | ✅ |
| Unstop | API | ✅ |
| RemoteOK | API | ✅ |
| WeWorkRemotely | RSS | ✅ |
| Indeed India | Scrape | ✅ |

## Setup (5 Steps)

### Step 1 — Create Telegram Bot
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. `My Job Alert Bot`)
4. Choose a username (e.g. `mybba_jobbot`)
5. Copy the **token** (looks like `110201543:AAHdqTcvCH1vGWJxfSeofSs4tHmC4v5pU`)

### Step 2 — Get Your Chat ID
1. Start your bot (send it `/start`)
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id": 123456789}` — that number is your **Chat ID**

### Step 3 — Get RapidAPI Key (for LinkedIn/Indeed — FREE tier)
1. Go to https://rapidapi.com
2. Sign up free
3. Search "JSearch" → Subscribe to free plan (200 req/month free)
4. Copy your API key from the dashboard

### Step 4 — Install & Run
```bash
# Install dependencies
pip3 install -r requirements.txt

# Set credentials
export TELEGRAM_BOT_TOKEN="110201543:AAHdqTcvCH1vGWJxfSeofSs4tHmC4v5pU"
export TELEGRAM_CHAT_ID="123456789"
export RAPIDAPI_KEY="your_rapidapi_key"   # optional

# Run the bot
python3 job_bot.py
```

### Step 5 — Keep it Running 24/7 (optional)

**On Linux/Mac:**
```bash
nohup python3 job_bot.py &
```

**On Windows:**
```
# Create run.bat
set TELEGRAM_BOT_TOKEN=your_token
set TELEGRAM_CHAT_ID=your_chat_id
set RAPIDAPI_KEY=your_key
python job_bot.py
```

**Free cloud hosting (Railway.app):**
1. Push to GitHub
2. Connect to Railway
3. Add env vars in Railway dashboard
4. Deploy!

## Filters Applied
- ✅ BBA / B.Com / Commerce / Business Admin keywords
- ✅ Fresher / Entry-level / 0-1 year experience
- ✅ Remote / Work from Home
- ❌ Excludes: Senior, 5+ years, 10+ years, Director roles

## Files
- `job_bot.py` — Main bot code
- `seen_jobs.json` — Auto-created; tracks sent jobs (no repeats)
- `job_bot.log` — Log file

## Telegram Message Format
```
🆕 Business Development Associate
🏢 XYZ Company
📍 Remote / Work from Home
💰 ₹15,000 - ₹25,000
🌐 Source: Internshala
🔗 Apply Here
🕐 24 Apr 2025 10:30 AM IST
```
# LinkedinRemoteScraper
