"""Chat with the bot locally (no WhatsApp account needed).

Interactive:   python tools/local_chat.py
Scripted:      python tools/local_chat.py --script "hi,1,1,Rajasthan,1,2,180000" [--number 919876543210] [--md out.md]
Every message goes through the real /whatsapp/webhook endpoint; replies are captured from a fake Graph API.
Script extras: "[919811112222] text" sends as another number; "{REF}" is replaced by the last REF- share code seen;
separate messages with "|" instead of "," when a message itself contains commas (use --sep "|").
"""
import argparse
import logging
import re

from _local import start, wa_in

logging.disable(logging.INFO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", help="comma-separated user messages")
    ap.add_argument("--number", default="919876543210")
    ap.add_argument("--md", help="write a markdown transcript to this file")
    ap.add_argument("--title", default="Sample conversation")
    ap.add_argument("--sep", default=",")
    ap.add_argument("--intro", default="")
    args = ap.parse_args()
    c, fake = start()
    lines, i = ([args.intro, ""] if args.intro else []), 0
    last_ref = {"code": ""}

    def say(text, number):
        nonlocal i
        i += 1
        before = len(fake.sent)
        c.post("/whatsapp/webhook", json=wa_in(number, text, f"wamid.IN{i}"))
        out = [m["text"]["body"] for m in fake.sent[before:] if m.get("type") == "text"]
        for o in out:
            m = re.search(r"REF-[A-Z0-9]+", o)
            if m:
                last_ref["code"] = m.group(0)
        return out

    msgs = args.script.split(args.sep) if args.script else None
    while True:
        if msgs is not None:
            if not msgs:
                break
            text = msgs.pop(0).strip()
        else:
            try:
                text = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if text in {"quit", "exit"}:
                break
        number, who = args.number, "Student"
        m = re.match(r"^\[(\d+)\]\s*(.*)$", text)
        if m:
            number, text, who = m.group(1), m.group(2), f"Friend (+{m.group(1)[:2]}…{m.group(1)[-4:]})"
        text = text.replace("{REF}", last_ref["code"])
        replies = say(text, number)
        print(f"\n👤 {text}")
        for r in replies:
            print(f"🤖 {r}")
        lines.append(f"**👤 {who}:** {text}\n")
        for r in replies:
            lines.append("**🤖 Bot:**\n\n```text\n" + r + "\n```\n")
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(f"# {args.title}\n\n" + "\n".join(lines))
        print(f"\nTranscript written to {args.md}")


if __name__ == "__main__":
    main()
