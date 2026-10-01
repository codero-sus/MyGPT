def register(api):
    @api.skill(
        "take_note",
        "Store a short note the user wants remembered as a fact.",
        pattern=r"^(note:|take a note|make a note)",
    )
    def take_note(ctx, text=""):
        msg = ctx.get("user") or text
        body = msg.split(":", 1)[-1].strip() if ":" in msg else msg
        store = ctx.get("store")
        if store is not None:
            store.add_fact("user", "note", body, 0.9)
        return f"Noted and stored as a fact: {body}"
