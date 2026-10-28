def register(api):
    @api.skill(
        "self_status",
        "Summarize who I am and how I am growing.",
        pattern=r"how (are|have) you (improving|growing|learning)",
    )
    def self_status(ctx, text=""):
        brain = ctx.get("brain")
        if brain is None:
            return "online"
        s = brain.stats()
        c = s["counters"]
        return (
            f"I'm MyGPT. Turns lived: {c['messages']}. Improvement cycles: "
            f"{c['cycles']}. Constitution v{s['constitution_version']} with "
            f"{s['principles']} principles. I hold {s['pairs']} memory pairs, "
            f"{s['facts']} facts and {s['lessons']} lessons. Last loss: "
            f"{s['last_loss']}."
        )
