"""The case workflow as one table.

Everything that can change a case goes through `decide()`. It is pure: no database, no web
framework. The API asks `possible()` which buttons to show, and `next_step()` what to tell
the person looking at the case, so the screen and the server can never disagree.

Statuses:
    flagged -> test_ordered -> confirmed_genetic
                            -> no_variant -> clinical_fh (DLCN 6 or more) | dismissed
    flagged -> dismissed (with a reason; can be reopened)

Consent and family testing are facts on a confirmed case, not extra statuses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

CONFIRMED = ("confirmed_genetic", "clinical_fh")
OPEN = ("flagged", "test_ordered")

# Staff roles. Lab and system are not people: they are how test results and timers enter.
ROLES = {
    "clinician": "Dr. Layla, lipid clinician",
    "coordinator": "Omar, family coordinator",
    "nurse": "Hind, Well-Child nurse",
    "lead": "Dr. Saeed, programme lead",
}
LAB, SYSTEM = "lab", "system"
ACTOR_NAME = {**ROLES, LAB: "Genetics lab (mock)", SYSTEM: "Heart Line"}

DISMISS_REASONS = {
    "secondary_cause": "Another cause explains the cholesterol",
    "known_fh": "FH already known and treated elsewhere",
    "result_error": "The result looks wrong",
    "other": "Other",
}


class Refusal(Exception):
    """A refused action. `kind` maps to an HTTP status; `code` is stable and maps to copy."""

    def __init__(self, kind: str, code: str, message: str):
        super().__init__(message)
        self.kind, self.code, self.message = kind, code, message


@dataclass(frozen=True)
class Transition:
    action: str
    label: str
    roles: tuple[str, ...]
    frm: tuple[str, ...]
    to: str | None = None                      # None: status stays the same
    guard: Callable[[dict], tuple | None] = lambda c: None  # None, or (code, sentence) when it blocks
    needs: tuple[str, ...] = ()                # inputs the caller must send
    primary: bool = False
    done: str = ""                             # what to tell the person afterwards
    event: str = ""                            # audit sentence


def _g(code: str, sentence: str, test: Callable[[dict], bool]):
    return lambda c: None if test(c) else (code, sentence)


def _all(*guards):
    def run(c):
        for g in guards:
            r = g(c)
            if r:
                return r
        return None
    return run


no_consent_yet = _g("consent_already_recorded", "Consent has already been recorded.", lambda c: c["consent"] is None)
consented = _g("no_consent", "The patient has not agreed to contacting relatives.", lambda c: c["consent"] == 1)
declined = _g("not_declined", "The patient has not declined.", lambda c: c["consent"] == 0)
not_started = _g("already_started", "Family testing has already started for this patient.", lambda c: not c["cascade_at"])
dlcn_6 = _g("dlcn_too_low", "Clinical FH needs a DLCN score of 6 or more.", lambda c: (c.get("dlcn_total") or 0) >= 6)
adult_case = _g("child_case", "For a child, the family is already in the programme through the parent.",
                lambda c: c.get("source") != "wellchild")
was_dismissed = _g("nothing_to_undo", "There is nothing to reopen.", lambda c: bool(c.get("prev_status")))

TABLE: tuple[Transition, ...] = (
    Transition("order_test", "Order genetic test", ("clinician",), ("flagged",), "test_ordered", primary=True,
               done="Genetic test ordered. The result is due in about two weeks and will appear under Results back.",
               event="Genetic test ordered"),
    Transition("dismiss", "Not FH", ("clinician",), ("flagged", "no_variant"), "dismissed", needs=("reason",),
               done="Closed. You can reopen it from this page.", event="Flag dismissed"),
    Transition("reopen", "Reopen", ("clinician",), ("dismissed",), None, guard=was_dismissed,
               done="Reopened.", event="Case reopened"),
    Transition("result_variant", "Variant found", (LAB,), ("test_ordered",), "confirmed_genetic",
               event="Genetic test result: variant found"),
    Transition("result_none", "No variant found", (LAB,), ("test_ordered",), "no_variant",
               event="Genetic test result: no variant found"),
    Transition("mark_clinical", "Record as clinical FH", ("clinician",), ("no_variant",), "clinical_fh", guard=dlcn_6,
               primary=True, done="Recorded as clinical FH. Next: ask the patient about family testing.",
               event="Recorded as clinical FH"),
    Transition("consent_yes", "Patient agrees", ("clinician",), CONFIRMED, None, guard=_all(adult_case, no_consent_yet), primary=True,
               done="Consent recorded and handed to the family coordinator, who will contact the relatives.",
               event="Patient agreed to family testing"),
    Transition("consent_no", "Patient declines", ("clinician",), CONFIRMED, None, guard=_all(adult_case, no_consent_yet),
               done="Recorded. Nobody will be contacted. This can be changed if the patient reconsiders.",
               event="Patient declined family testing"),
    Transition("consent_reopen", "Patient has reconsidered", ("clinician",), CONFIRMED, None,
               guard=_all(declined, not_started), done="Consent reopened. Ask again when the patient is ready.",
               event="Consent question reopened"),
    Transition("start_cascade", "Send invitations", ("coordinator",), CONFIRMED, None,
               guard=_all(consented, not_started), primary=True,
               done="Invitations sent. Children were flagged for their Well-Child Visit. Replies appear on this page.",
               event="Family testing started"),
)
BY_ACTION = {t.action: t for t in TABLE}


@dataclass
class Decision:
    transition: Transition
    set: dict = field(default_factory=dict)   # case columns to change
    detail: dict = field(default_factory=dict)  # goes into the audit row
    run: str | None = None                    # a side effect the caller applies ("start_cascade")


def decide(case: dict, role: str, action: str, inputs: dict | None = None) -> Decision:
    """Accept or refuse one action on one case. Raises Refusal; never touches storage."""
    inputs = inputs or {}
    t = BY_ACTION.get(action)
    if t is None:
        raise Refusal("validation", "unknown_action", f"Unknown action: {action}")
    if role not in t.roles:
        who = " or ".join(ACTOR_NAME[r].split(", ")[-1] for r in t.roles)
        raise Refusal("permission", "wrong_role", f"Only the {who} can do this.")
    if case["status"] not in t.frm:
        raise Refusal("business", "wrong_status", "This step is not available at this stage of the case.")
    blocked = t.guard(case)
    if blocked:
        raise Refusal("business", blocked[0], blocked[1])
    for need in t.needs:
        if not inputs.get(need):
            raise Refusal("validation", f"missing_{need}", f"A {need} is needed for this step.")

    d = Decision(t)
    if t.to:
        d.set["status"] = t.to
    if action == "dismiss":
        if inputs["reason"] not in DISMISS_REASONS:
            raise Refusal("validation", "bad_reason", "Choose one of the listed reasons.")
        d.set.update(prev_status=case["status"], dismiss_reason=inputs["reason"])
        d.detail = {"reason": DISMISS_REASONS[inputs["reason"]], "note": inputs.get("note")}
    elif action == "reopen":
        d.set.update(status=case["prev_status"], prev_status=None, dismiss_reason=None)
    elif action == "order_test":
        d.set["test_due"] = inputs.get("due")
        d.detail = {"result_due": inputs.get("due")}
    elif action == "result_variant":
        d.set["found_variant"] = inputs.get("variant")
        d.detail = {"found_variant": inputs.get("variant")}
    elif action == "consent_yes":
        excluded = [int(x) for x in inputs.get("exclude") or []]
        d.set.update(consent=1, consent_excluded=excluded)
        d.detail = {"relatives_excluded_by_patient": len(excluded)}
    elif action == "consent_no":
        d.set.update(consent=0)
    elif action == "consent_reopen":
        d.set.update(consent=None)
    elif action == "start_cascade":
        d.run = "start_cascade"
    return d


def possible(case: dict, role: str) -> list[dict]:
    """The actions this role can take on this case right now. The same checks as decide()."""
    out = []
    for t in TABLE:
        if role in t.roles and case["status"] in t.frm and t.guard(case) is None:
            out.append({"id": t.action, "label": t.label, "primary": t.primary, "needs": list(t.needs)})
    return out


def next_step(case: dict, role: str) -> dict:
    """What to tell this person about this case: a title, one or two sentences, and who it waits on."""
    s, consent = case["status"], case["consent"]
    found = (f"Confirmed: {case['found_variant']}." if case.get("found_variant") else "Confirmed as clinical FH.")
    mine = {a["id"] for a in possible(case, role)}

    def step(key, title, detail, waiting_on=None):
        return {"key": key, "title": title, "detail": detail, "waiting_on": waiting_on}

    if s == "flagged":
        if "order_test" in mine:
            return step("review", "Review this flag", "If the reasons fit, order a genetic test. It takes about two weeks.")
        return step("review", "Waiting for clinical review", "A clinician has not reviewed this flag yet.", "clinician")
    if s == "test_ordered":
        return step("waiting_test", "Waiting for the genetic test",
                    f"Result expected by {case.get('test_due_text') or case.get('test_due')}.", "lab")
    if s == "no_variant":
        if "mark_clinical" in mine:
            return step("no_variant", "No variant found",
                        "The DLCN score is 6 or more, so this can still be recorded as clinical FH.")
        if "dismiss" in mine:
            return step("no_variant", "No variant found", "The DLCN score is below 6. Close the case with a reason.")
        return step("no_variant", "No variant found", "Waiting for the clinician to close or reclassify.", "clinician")
    if s == "dismissed":
        why = DISMISS_REASONS.get(case.get("dismiss_reason") or "", "")
        return step("dismissed", "Closed", f"Reason: {why}." if why else "No further action.")
    # Confirmed.
    if case.get("source") == "wellchild":
        return step("child", "Confirmed at a Well-Child Visit",
                    f"{found} Refer to the paediatric lipid clinic. The family is already in the programme.")
    if consent is None:
        if "consent_yes" in mine:
            return step("consent", "Ask about family testing", found)
        return step("consent", "Waiting for the patient's answer",
                    f"{found} The clinician has not yet asked the patient about family testing.", "clinician")
    if consent == 0:
        return step("declined", "Family testing declined", f"{found} Nobody has been contacted.")
    if not case["cascade_at"]:
        if "start_cascade" in mine:
            return step("start", "Review and send invitations", "The patient agreed. Check who will be contacted, then send.")
        return step("start", "Handed to the family coordinator",
                    f"{found} The patient agreed. The coordinator will contact the relatives.", "coordinator")
    return step("running", "Family testing under way", found)
