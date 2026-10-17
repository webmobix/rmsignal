"""How figures are written in code-built text, and the checks that agent prose quotes only computed figures."""

import re

from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers

LOSS_WORDS = re.compile(r"\b(loss|losses|lose|loses|fall|falls|fell|decline|declines|declined|drop|drops|dropped|decrease|decreases|down)\b", re.I)
GAIN_WORDS = re.compile(r"\b(gain|gains|rise|rises|rose|increase|increases|increased|advance|advances|up|benefit|benefits)\b", re.I)


def fmt_usd(x: float) -> str:
    a = abs(x)
    body = f"{a / 1e9:.2f}bn" if a >= 1e9 else f"{a / 1e6:.2f}m" if a >= 1e6 else f"{a / 1e3:.0f}k" if a >= 1e3 else f"{a:.0f}"
    return f"{'-' if x < 0 else ''}USD {body}"


def fmt_pct(x: float, signed: bool = True) -> str:
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"


def figure_problems(text: str, figures: dict, *, direction: float | None = None) -> list[str]:
    """Why ``text`` quotes something other than a computed figure.

    ``figures`` holds every computed value the text may quote (nested dicts and lists of numbers). Numbers are compared by value
    within the output guard's tolerance. ``direction`` is the sign of the headline change: prose that speaks only of losses when the
    change is a gain (or the reverse) is a problem too, since the numeric comparison ignores signs."""
    problems = []
    bad = unsupported_numbers(text, evidence_numbers(figures))
    if bad:
        problems.append("figure(s) " + ", ".join(f"{b:g}" for b in bad) + " are not computed values")
    if direction:
        loss, gain = bool(LOSS_WORDS.search(text)), bool(GAIN_WORDS.search(text))
        if direction > 0 and loss and not gain:
            problems.append("describes a loss where the computed change is a gain")
        if direction < 0 and gain and not loss:
            problems.append("describes a gain where the computed change is a loss")
    return problems
