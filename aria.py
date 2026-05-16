#!/usr/bin/env python3
"""ARIA — Algorithm Research & Intelligence Agent

Runs weekly, researches Instagram and TikTok algorithm changes via Claude's
native web_search tool, and emails a structured briefing.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are ARIA, a specialist research and briefing agent focused exclusively on \
Instagram and TikTok algorithms. You work for Jaiden, a 22-year-old entrepreneur \
based in Dubai who is building a personal brand and an AI consulting business. \
He is strategically sharp but non-technical when it comes to social media platforms.

Your job is to produce a daily briefing that keeps Jaiden current on algorithm \
changes and content strategy signals across Instagram and TikTok.

Your briefings must be:
- Based only on information from the last 24 hours
- Written in plain, direct English — no jargon, no filler
- Honest about uncertainty: clearly distinguish confirmed changes from observed patterns
- Actionable: always end with a clear recommendation or an honest "no change needed"
- Concise: readable in under 5 minutes

You are not a content creator. You do not write posts. You are an intelligence advisor.

If you find no meaningful new information this week, say so plainly. \
Do not fabricate or recycle old findings to fill space.\
"""

USER_PROMPT_TEMPLATE = """\
Today is {date}.

Search the web for the latest Instagram and TikTok algorithm news published in \
the last 24 hours. Cover all five areas below — run separate searches for each:

1. Instagram algorithm changes or updates
2. TikTok algorithm changes or updates
3. Instagram Reels reach and engagement changes this week
4. TikTok For You Page algorithm update
5. Social media algorithm news this week (broad sweep)

Prioritise: official platform announcements, multiple independent sources \
corroborating the same finding, and commentary from credible creators or \
industry publications (Social Media Today, Later, Hootsuite Blog, Sprout Social).

Deprioritise: recycled or undated content, speculative takes without evidence, \
engagement bait framed as "algorithm secrets".

Then produce the weekly ARIA briefing using exactly this structure:

ARIA DAILY BRIEF — {date}
Instagram & TikTok Algorithm Intelligence

---
THIS WEEK IN BRIEF
[2–3 sentence summary of the most important developments this week. \
Write for someone who may only read this section.]

---
INSTAGRAM
[Concise summary of any confirmed or emerging algorithm developments this week. \
Cite sources where relevant. End with one line: what this means for posting behaviour.]

---
TIKTOK
[Same structure as Instagram section above.]

---
CONTENT FORMAT SIGNALS
[Which formats — Reels, carousels, long-form video, etc. — are showing \
increased or decreased reach based on current signals.]

---
THIS WEEK'S RECOMMENDED ADJUSTMENT
[One clear, actionable recommendation. If nothing changed meaningfully, state: \
"No adjustment needed this week — current strategy remains valid."]

---
SOURCES
[List key sources referenced, with URLs where available.]

If any section has no new information this week, write \
"Nothing significant to report this week" rather than speculating.\
"""


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

def run_research() -> str:
    """Run ARIA's research loop and return the completed briefing text."""
    client = anthropic.Anthropic()
    today = datetime.now().strftime("%d %B %Y")

    messages: list[dict] = [
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(date=today)}
    ]

    # The web_search tool runs server-side — Claude issues queries, Anthropic
    # fetches results, and the server loops automatically. The client only needs
    # to handle pause_turn (server loop hit its 10-iteration cap) by re-sending.
    while True:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            temperature=0.3,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    # Cache the system prompt — it never changes between runs,
                    # so every weekly run reads from cache after the first write.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "pause_turn":
            # Server loop paused — append assistant turn and continue
            messages.append({"role": "assistant", "content": response.content})
            continue

        # Unexpected stop reason — exit loop
        print(f"Unexpected stop_reason: {response.stop_reason}")
        break

    briefing = next(
        (block.text for block in response.content if block.type == "text"), ""
    )

    cache_hits = response.usage.cache_read_input_tokens
    cache_written = response.usage.cache_creation_input_tokens
    print(
        f"Usage — input: {response.usage.input_tokens} | "
        f"cache read: {cache_hits} | cache written: {cache_written} | "
        f"output: {response.usage.output_tokens}"
    )

    return briefing


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

def send_email(briefing: str, date: str) -> None:
    """Send the briefing via Gmail SMTP with an app password."""
    sender = os.environ["GMAIL_ADDRESS"]
    recipient = os.environ["RECIPIENT_EMAIL"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"ARIA Daily Brief — {date}"
    msg["From"] = f"ARIA <{sender}>"
    msg["To"] = recipient

    msg.attach(MIMEText(briefing, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Briefing delivered to {recipient}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"ARIA starting — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    briefing = run_research()

    if not briefing.strip():
        print("Error: no briefing text was generated. Aborting.")
        return

    print(f"\n{'=' * 60}\n{briefing}\n{'=' * 60}\n")

    today = datetime.now().strftime("%d %B %Y")
    send_email(briefing, today)
    print("ARIA run complete.")


if __name__ == "__main__":
    main()
