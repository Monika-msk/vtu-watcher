

# VTU Internship Watcher

Hey there! 👋

This is a little Python script that keeps an eye on the latest internship postings from VTU’s internship API. It checks every 30 minutes (or however often you want), and if it finds any new internships, it sends you an email right away so you don’t miss out.

## Why did I make this?

Because internships get filled fast, and being the first to know can make all the difference! Instead of constantly refreshing the website, this script does the work for you — quietly running in the background and giving you a heads-up by email.

## How does it work?

* It fetches internship listings from the VTU API page by page.
* Keeps track of what it’s already seen (so you don’t get spammed).
* Sends you an email **only** when there are new postings.
* Logs what it’s doing and any errors, so you can check if something goes wrong.
* Runs automatically using GitHub Actions — so it keeps working even if your computer is off.

## What you need to do

1. **Set up your Gmail app password** — the script uses this to send emails securely.
2. **Add your email and Gmail credentials as GitHub Secrets** in your repo settings.
3. **Adjust the schedule** in the GitHub Actions workflow to check how often you want (every 30 minutes, hourly, etc.).
4. Sit back and wait for emails about new internships!

## How to get started

* Clone this repo.
* Customize your email credentials as environment variables or GitHub secrets.
* Commit and push the code to trigger GitHub Actions.
* Check your email when new internships pop up!


