#!/usr/bin/env python3
"""
Single-run watcher: fetch pages from API, detect new items, email them,
and update seen.json. Meant to be run from GitHub Actions or locally.
"""

import os, json, time, hashlib, smtplib, sys
from email.message import EmailMessage
from urllib.parse import urlparse, urljoin
import requests

# ---------- CONFIG ----------
API_BASE = os.getenv("API_URL", "https://vtuapi.internyet.in/api/v1/internships")
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))     # how many pages to fetch (increase if needed)
SEEN_FILE = "seen.json"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

DEBUG = os.getenv("DEBUG", "") != ""

# ---------- helpers ----------
def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)

def save_seen(seen_set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen_set)), f, indent=2, ensure_ascii=False)

def make_id(item):
    # Prefer explicit id field, else hash title+company+link
    for k in ("id", "_id", "internship_id"):
        if isinstance(item, dict) and k in item and item[k]:
            return str(item[k])
    title = item.get("title") or item.get("name") or item.get("position") or ""
    link = item.get("link") or item.get("url") or item.get("slug") or ""
    s = (title + "|" + str(link))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def infer_title(item):
    return item.get("title") or item.get("name") or item.get("position") or "Internship"

def infer_link(item):
    # try common fields; if slug, join with site root
    for k in ("url","link","job_url","application_url"):
        if item.get(k):
            return item.get(k)
    slug = item.get("slug") or item.get("path")
    if slug:
        base = "https://vtu.internyet.in"
        return urljoin(base, slug)
    # fallback: return API item id so at least something
    return f"https://vtu.internyet.in/internships"

def send_email_plain(subject, body_text):
    if not SMTP_USER or not SMTP_PASS or not EMAIL_TO:
        print("Email not configured. Set SMTP_USER, SMTP_PASS, EMAIL_TO.")
        return
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body_text)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)
    print("Email sent:", subject)

# ---------- main ----------
def fetch_page(page):
    # Build page URL (some APIs accept ?page=)
    if "?" in API_BASE:
        url = API_BASE.split("?")[0] + f"?page={page}"
    else:
        url = API_BASE.rstrip("/") + f"?page={page}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/115.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_items_from_response(resp_json):
    if resp_json is None:
        return []

    if isinstance(resp_json, dict):
        # Case: data contains internships directly
        if isinstance(resp_json.get("data"), list):
            return resp_json["data"]

        # Case: data is an object containing a "data" list
        if isinstance(resp_json.get("data"), dict) and isinstance(resp_json["data"].get("data"), list):
            return resp_json["data"]["data"]

        # Other known keys
        if "internships" in resp_json and isinstance(resp_json["internships"], list):
            return resp_json["internships"]

        # fallback: first list inside
        for v in resp_json.values():
            if isinstance(v, list):
                return v
        return []

    if isinstance(resp_json, list):
        return resp_json

    return []


def main():
    if DEBUG:
        print("DEBUG mode ON")

    seen = load_seen()
    newly_seen = []
    page = 1
    total_fetched = 0

    for page in range(1, MAX_PAGES + 1):
        try:
            resp = fetch_page(page)
        except Exception as e:
            print(f"Failed to fetch page {page}: {e}")
            break
        items = extract_items_from_response(resp)
        if DEBUG:
            print(f"page {page} -> {len(items)} items")
            if page == 1:
                print("sample item (raw):", json.dumps(items[0] if items else {}, indent=2, ensure_ascii=False))
        if not items:
            break
        total_fetched += len(items)
        for it in items:
            uid = make_id(it)
            if uid not in seen:
                seen.add(uid)
                newly_seen.append((uid, it))
        # if API returns fewer than page-size it may be last page; continue or break is fine
    print(f"Fetched {total_fetched} items; new found: {len(newly_seen)}")

    # If running first time and you don't want alerts for existing items,
    # run locally once with DEBUG=1, then commit seen.json before enabling Actions.
    if newly_seen:
        for uid, it in newly_seen:
            title = infer_title(it)
            link = infer_link(it)
            body = f"{title}\n{link}\n\nRaw: {json.dumps(it, ensure_ascii=False)}"
            print("New:", title, link)
            try:
                send_email_plain(f"New VTU Internship: {title}", body)
            except Exception as e:
                print("Email send failed:", e)
    else:
        print("No new internships.")

    save_seen(seen)
    if DEBUG:
        print("Saved seen.json with", len(seen), "items")

if __name__ == "__main__":
    main()
