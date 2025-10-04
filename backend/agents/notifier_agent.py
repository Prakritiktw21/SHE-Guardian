# notifier_agent.py: sends alerts (Telegram/Email hooks can be added)
def send_alert(summary: str, contacts=None):
    print("[ALERT]", summary)
    # This is a placeholder; real alerts are sent from server.py via Telegram.
    # You can wire email/SMTP or WhatsApp APIs here if needed.
