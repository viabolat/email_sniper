import os
import feedparser
import requests
import time
import resend
from dotenv import load_dotenv

load_dotenv()

# 1. Resend API Setup
resend.api_key = os.environ["RESEND_API_KEY"]
YOUR_EMAIL = os.environ.get("YOUR_EMAIL")

# 2. Target Settings
SUBREDDITS = "denver+eventplanning"

# Positive intent keywords (buyers looking for help/space)
KEYWORDS = [
    "looking for venue", 
    "recommendation for event", 
    "av company", 
    "event space", 
    "venue recommendation",
    "corporate event",
    "venue for party",
    "retreat space",
    "looking for an av",
    "venue for 50",
    "venue for 100",
    "private room"
]

# Negative keywords to DROP junk/promotional posts
EXCLUDE_KEYWORDS = [
    "comedy night",
    "comedy show",
    "ticket",
    "festival",
    "performing live",
    "live music",
    "stand up",
    "open mic",
    "hiring",
    "free entry"
]

seen_post_ids = set()
RSS_URL = f"https://www.reddit.com/r/{SUBREDDITS}/new/.rss"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 EventSniper/1.0'
}

def send_email_alert(title, url, text):
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": YOUR_EMAIL,
            "subject": f"🎯 Reddit Intent: {title[:50]}...",
            "html": f"""
                <h2>{title}</h2>
                <p><strong>Post Content Preview:</strong> {text[:300]}...</p>
                <p><a href="{url}" style="background-color: #0077b5; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px;">View Reddit Post</a></p>
            """
        })
        print(f"✅ Email alert sent: {title}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def check_reddit_rss():
    try:
        response = requests.get(RSS_URL, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            print(f"[{time.strftime('%H:%M:%S')}] Checked Reddit RSS — {len(feed.entries)} posts inspected.")
            
            for entry in feed.entries:
                post_id = entry.id
                
                if post_id in seen_post_ids:
                    continue
                
                seen_post_ids.add(post_id)
                
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                content = f"{title} {summary}".lower()
                
                # Filter check
                has_keyword = any(k in content for k in KEYWORDS)
                has_exclusion = any(e in content for e in EXCLUDE_KEYWORDS)
                
                if has_keyword and not has_exclusion:
                    post_url = entry.get('link', '')
                    print(f"\n🎯 HIGH-INTENT MATCH FOUND: {title}")
                    send_email_alert(title, post_url, summary)
                    
        elif response.status_code == 429:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Rate limited (429). Pausing for 3 minutes...")
            time.sleep(180)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Status code: {response.status_code}")
            
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Connection error: {e}")

print("🚀 Tuned Intent Sniper is active...")
print(f"Monitoring r/{SUBREDDITS} every 3 minutes...\n")

while True:
    check_reddit_rss()
    time.sleep(180)