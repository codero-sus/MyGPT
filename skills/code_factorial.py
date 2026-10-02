"""Auto-written by MyGPT's coding agent after repeated `factorial` tasks."""

def register(api):
    @api.skill(
        'code_factorial',
        "Learned coding skill: factorial (written by the coding agent).",
        pattern='factorial(?: of)? (\\d+)|(\\d+)!',
    )
    def code_factorial(ctx, text=""):
        from mygpt.coding import solve
        r = solve(ctx.get("user") or text)
        if r and r["ok"]:
            return f"\u2705 {r['answer']}  (learned skill: factorial)"
        return "The learned skill could not solve that one."
