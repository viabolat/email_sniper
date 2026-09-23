import argparse
import json
import os
import sys
import time
import feedparser # type: ignore
import requests # type: ignore
import resend # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()

# 1. Resend API Setup
resend.api_key = os.environ.get("RESEND_API_KEY")
YOUR_EMAIL = os.environ.get("YOUR_EMAIL")

CONFIG_FILE = "industries.json"
seen_post_ids = set()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 IntentSniper/1.0'
}

def parse_args():
    parser = argparse.ArgumentParser(description="Multi-Industry Intent Sniper")
    
    # Allows passing multiple positional targets: python3 sniper.py automation_leads upwork_intent
    parser.add_argument(
        "industry_positional",
        nargs="*",
        type=str,
        help="Target industry keys (e.g., automation_leads upwork_intent)."
    )
    
    # Allows passing multiple flag targets: python3 sniper.py -i automation_leads upwork_intent
    parser.add_argument(
        "-i", "--industry",
        nargs="+",
        type=str,
        help="Target industry keys via flag."
    )
    
    args = parser.parse_args()
    targets = args.industry or args.industry_positional
    return argparse.Namespace(industries=targets)

def load_industry_config(filepath, target_industries=None):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Config file '{filepath}' missing in root directory.")
    
    with open(filepath, "r", encoding="utf-8") as f:
        all_industries = json.load(f)

    if target_industries:
        selected = {}
        for target in target_industries:
            if target not in all_industries:
                available = ", ".join(all_industries.keys())
                print(f"❌ Error: Industry '{target}' not found in {filepath}.")
                print(f"Available industries: {available}")
                sys.exit(1)
            selected[target] = all_industries[target]
        return selected
    
    return all_industries

def send_email_alert(industry_name, title, url, text):
    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": YOUR_EMAIL,
            "subject": f" [{industry_name.upper()}] Intent: {title[:45]}...",
            "html": f"""
                <h2>[{industry_name.replace('_', ' ').title()}] Match</h2>
                <h3>{title}</h3>
                <p><strong>Content Preview:</strong> {text[:300]}...</p>
                <p><a href="{url}" style="background-color: #0077b5; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px;">View Post / Job Lead</a></p>
            """
        })
        print(f"✅ Email alert sent for [{industry_name}]: {title}")
    except Exception as e:
        print(f"❌ Failed to send email for [{industry_name}]: {e}")

def check_feeds(industries):
    for industry_name, config in industries.items():
        keywords = config.get("keywords", [])
        exclude_keywords = config.get("exclude_keywords", [])
        
        # Determine feed URL: Custom RSS URL (Upwork/Custom) vs standard Reddit subreddits
        if "rss_override" in config:
            rss_url = config["rss_override"]
            source_label = "Custom RSS"
        else:
            subreddits = config.get("subreddits", "")
            rss_url = f"https://www.reddit.com/r/{subreddits}/new/.rss"
            source_label = f"r/{subreddits}"
        
        try:
            response = requests.get(rss_url, headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                print(f"[{time.strftime('%H:%M:%S')}] Checked [{industry_name}] ({source_label}) — {len(feed.entries)} entries inspected.")
                
                for entry in feed.entries:
                    post_id = entry.get('id', entry.get('link', ''))
                    
                    if not post_id or post_id in seen_post_ids:
                        continue
                    
                    seen_post_ids.add(post_id)
                    
                    title = entry.get('title', '')
                    summary = entry.get('summary', '')
                    content = f"{title} {summary}".lower()
                    
                    print(f"  > [{industry_name}] Inspecting: {title[:60]}...")
                    
                    has_keyword = any(k.lower() in content for k in keywords)
                    has_exclusion = any(e.lower() in content for e in exclude_keywords)
                    
                    if has_keyword and not has_exclusion:
                        post_url = entry.get('link', '')
                        print(f"\n HIGH-INTENT MATCH FOUND [{industry_name}]: {title}")
                        send_email_alert(industry_name, title, post_url, summary)
                        
            elif response.status_code == 429:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Rate limited (429) on [{industry_name}]. Pausing 3 minutes...")
                time.sleep(180)
            elif response.status_code in [502, 503, 504]:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Server error ({response.status_code}) on [{industry_name}]. Retrying in 10s...")
                time.sleep(10)
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Status code {response.status_code} on [{industry_name}]")
                
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Connection error on [{industry_name}]: {e}")

if __name__ == "__main__":
    args = parse_args()
    
    if args.industries:
        targets_str = ", ".join(args.industries)
        print(f"[ACTIVE] Intent Sniper — Targeted Industries: [{targets_str}]")
    else:
        print("[ACTIVE] Intent Sniper — Scanning ALL industries in industries.json")

    while True:
        try:
            industry_configs = load_industry_config(CONFIG_FILE, target_industries=args.industries)
            check_feeds(industry_configs)
        except Exception as err:
            print(f"❌ Execution error: {err}")
            
        print(f"\nSleeping for 3 minutes before next check...\n")
        time.sleep(180)