"""The workflow table, tested without a database."""
import itertools
import unittest

from heartline import machine
from heartline.machine import Refusal

STATUSES = ("flagged", "test_ordered", "no_variant", "confirmed_genetic", "clinical_fh", "dismissed")
ROLES = (*machine.ROLES, machine.LAB, machine.SYSTEM)
INPUTS = {"reason": "other", "variant": "LDLR test", "due": "2026-12-01"}


def cases():
    for status, consent, started, dlcn, source in itertools.product(
            STATUSES, (None, 0, 1), (None, "2026-11-20"), (4, 7), ("detection", "cascade", "wellchild")):
        yield {"status": status, "consent": consent, "cascade_at": started, "dlcn_total": dlcn, "source": source,
               "prev_status": "flagged" if status == "dismissed" else None, "found_variant": None,
               "dismiss_reason": None, "consent_excluded": []}


class MachineTest(unittest.TestCase):
    def test_buttons_shown_are_exactly_what_the_server_accepts(self):
        n = 0
        for case in cases():
            for role in ROLES:
                offered = {a["id"] for a in machine.possible(case, role)}
                for action in machine.BY_ACTION:
                    try:
                        machine.decide(case, role, action, INPUTS)
                        accepted = True
                    except Refusal:
                        accepted = False
                    self.assertEqual(action in offered, accepted, (case, role, action))
                    n += 1
        self.assertGreater(n, 5000)

    def test_nothing_reaches_relatives_without_confirmation_and_consent(self):
        for case in cases():
            ok = any(a["id"] == "start_cascade" for a in machine.possible(case, "coordinator"))
            if ok:
                self.assertIn(case["status"], machine.CONFIRMED)
                self.assertEqual(case["consent"], 1)
                self.assertIsNone(case["cascade_at"])

    def test_only_the_coordinator_contacts_relatives_and_only_a_clinician_records_consent(self):
        t = machine.BY_ACTION
        self.assertEqual(t["start_cascade"].roles, ("coordinator",))
        for a in ("consent_yes", "consent_no", "order_test", "dismiss", "mark_clinical"):
            self.assertEqual(t[a].roles, ("clinician",))
        for a in ("result_variant", "result_none"):
            self.assertEqual(t[a].roles, (machine.LAB,))

    def test_refusals_carry_a_kind_and_a_code(self):
        case = next(cases())
        with self.assertRaises(Refusal) as r:
            machine.decide(case, "coordinator", "order_test")
        self.assertEqual((r.exception.kind, r.exception.code), ("permission", "wrong_role"))
        with self.assertRaises(Refusal) as r:
            machine.decide(case, "clinician", "dismiss", {})
        self.assertEqual((r.exception.kind, r.exception.code), ("validation", "missing_reason"))
        with self.assertRaises(Refusal) as r:
            machine.decide(case, "clinician", "mark_clinical")
        self.assertEqual(r.exception.kind, "business")

    def test_dismiss_can_be_reopened_to_where_it_was(self):
        case = {**next(cases()), "status": "no_variant"}
        d = machine.decide(case, "clinician", "dismiss", {"reason": "secondary_cause"})
        self.assertEqual(d.set["prev_status"], "no_variant")
        closed = {**case, **d.set}
        self.assertEqual(machine.decide(closed, "clinician", "reopen").set["status"], "no_variant")

    def test_every_state_has_a_next_step_for_every_staff_role(self):
        for case in cases():
            for role in machine.ROLES:
                step = machine.next_step(case, role)
                self.assertTrue(step["title"] and step["detail"], (case, role))


if __name__ == "__main__":
    unittest.main()
