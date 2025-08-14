import os
import json
import time
import hashlib
import smtplib
import sys
import logging
from email.message import EmailMessage
from urllib.parse import urljoin
import requests

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("watcher.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- Config ---
API_BASE = os.getenv("API_URL", "https://vtuapi.internyet.in/api/v1/internships")
MAX_PAGES = int(os.getenv("MAX_PAGES", "20"))
SEEN_FILE = "seen.json"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

DEBUG = os.getenv("DEBUG", "") != ""


# --- Helper Functions ---
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
    for k in ("url", "link", "job_url", "application_url"):
        if item.get(k):
            return item.get(k)
    slug = item.get("slug") or item.get("path")
    if slug:
        base = "https://vtu.internyet.in"
        return urljoin(base, slug)
    return "https://vtu.internyet.in/internships"


def send_email_plain(subject, body):
    if not SMTP_USER or not SMTP_PASS or not EMAIL_TO:
        logging.warning("Email not configured. Set SMTP_USER, SMTP_PASS, EMAIL_TO.")
        return
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


def send_email_with_retry(subject, body, retries=3, delay=5):
    for attempt in range(retries):
        try:
            send_email_plain(subject, body)
            logging.info(f"✅ Email sent: {subject}")
            break
        except Exception as e:
            logging.error(f"❌ Email send failed (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logging.error("Giving up sending email.")


def fetch_page(page):
    if "?" in API_BASE:
        url = API_BASE.split("?")[0] + f"?page={page}"
    else:
        url = API_BASE.rstrip("/") + f"?page={page}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_page_with_retry(page, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return fetch_page(page)
        except Exception as e:
            logging.error(f"Fetch page {page} failed (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def extract_items_from_response(resp_json):
    if resp_json is None:
        return []

    if isinstance(resp_json, dict):
        if isinstance(resp_json.get("data"), list):
            return resp_json["data"]
        if isinstance(resp_json.get("data"), dict) and isinstance(resp_json["data"].get("data"), list):
            return resp_json["data"]["data"]
        if "internships" in resp_json and isinstance(resp_json["internships"], list):
            return resp_json["internships"]
        for v in resp_json.values():
            if isinstance(v, list):
                return v
        return []

    if isinstance(resp_json, list):
        return resp_json

    return []


# --- Main Script ---
def main():
    if DEBUG:
        logging.info("DEBUG mode ON")

    seen = load_seen()
    total_fetched = 0
    new_count = 0

    for page in range(1, MAX_PAGES + 1):
        try:
            resp = fetch_page_with_retry(page)
        except Exception as e:
            logging.error(f"Failed to fetch page {page}: {e}")
            break

        items = extract_items_from_response(resp)

        if DEBUG:
            logging.info(f"Page {page} -> {len(items)} items")
            if page == 1 and items:
                logging.info(f"Sample item: {json.dumps(items[0], indent=2, ensure_ascii=False)}")

        if not items:
            break

        total_fetched += len(items)

        for it in items:
            uid = make_id(it)
            if uid not in seen:
                seen.add(uid)
                save_seen(seen)  # ✅ Save immediately to prevent duplicates if crash
                new_count += 1

                title = infer_title(it)
                link = infer_link(it)
                body = f"{title}\n{link}\n\nRaw: {json.dumps(it, ensure_ascii=False)}"
                logging.info(f"🆕 New internship: {title} {link}")

                send_email_with_retry(f"New VTU Internship: {title}", body)

    logging.info(f"📊 Summary: {total_fetched} fetched, {new_count} new.")


if __name__ == "__main__":
    main()
