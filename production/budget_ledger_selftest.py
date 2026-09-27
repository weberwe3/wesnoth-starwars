"""Restart, reservation, and exhaustion fixtures for the budget ledger."""

from pathlib import Path
import tempfile
import unittest

from budget_ledger import BudgetError, BudgetLedger, RESOURCES


SHA = "a" * 64
LIMITS = {"model_calls": 10, "elapsed_seconds": 100,
          "engine_runs": 4, "repair_attempts": 2, "disk_bytes": 1000,
          "completion_cutoff_model_calls": 6,
          "completion_reserve_model_calls": 4}


def units(**values):
    return {key: values.get(key, 0) for key in RESOURCES}


class BudgetLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "agent/runtime/unattended-budget.json"
        self.ledger = BudgetLedger(self.path, SHA, LIMITS, create=True)

    def test_restart_keeps_inflight_reservation_and_usage(self) -> None:
        self.ledger.reserve("ticket-001", "expansion", units(model_calls=2, engine_runs=1))
        again = BudgetLedger(self.path, SHA, LIMITS)
        self.assertEqual(again.read()["reservations"]["ticket-001"]["units"]["model_calls"], 2)
        again.settle("ticket-001", units(model_calls=2, engine_runs=1))
        self.assertEqual(BudgetLedger(self.path, SHA, LIMITS).read()["spent"]["model_calls"], 2)

    def test_idempotent_reserve_and_settle_cannot_double_charge(self) -> None:
        first = self.ledger.reserve("ticket-001", "expansion", units(model_calls=2))
        self.assertEqual(self.ledger.reserve("ticket-001", "expansion", units(model_calls=2))["revision"], first["revision"])
        settled = self.ledger.settle("ticket-001", units(model_calls=1))
        self.assertEqual(self.ledger.settle("ticket-001", units(model_calls=1))["revision"], settled["revision"])
        with self.assertRaisesRegex(BudgetError, "changed"):
            self.ledger.settle("ticket-001", units(model_calls=2))

    def test_expansion_stops_at_cutoff_while_delivery_can_use_reserve(self) -> None:
        self.ledger.reserve("ticket-001", "expansion", units(model_calls=6))
        with self.assertRaisesRegex(BudgetError, "completion cutoff"):
            self.ledger.reserve("ticket-002", "expansion", units(model_calls=1))
        self.ledger.reserve("delivery-001", "delivery", units(model_calls=4))
        with self.assertRaisesRegex(BudgetError, "limit"):
            self.ledger.reserve("delivery-002", "delivery", units(model_calls=1))

    def test_unsettled_action_remains_reserved_after_restart(self) -> None:
        self.ledger.reserve("engine-001", "integration", units(engine_runs=4))
        again = BudgetLedger(self.path, SHA, LIMITS)
        with self.assertRaisesRegex(BudgetError, "limit"):
            again.reserve("engine-002", "integration", units(engine_runs=1))

    def test_actual_overrun_is_recorded_and_blocks_new_actions(self) -> None:
        self.ledger.reserve("ticket-001", "expansion", units(model_calls=1))
        state = self.ledger.settle("ticket-001", units(model_calls=11))
        self.assertTrue(state["breached"])
        self.assertEqual(state["spent"]["model_calls"], 11)
        with self.assertRaisesRegex(BudgetError, "breached"):
            self.ledger.reserve("ticket-002", "delivery", units(model_calls=1))

    def test_different_charter_or_corrupt_state_cannot_reset_budget(self) -> None:
        self.ledger.reserve("ticket-001", "expansion", units(model_calls=1))
        with self.assertRaisesRegex(BudgetError, "identity"):
            BudgetLedger(self.path, "b" * 64, LIMITS)
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(BudgetError, "cannot be read"):
            BudgetLedger(self.path, SHA, LIMITS)

    def test_missing_ledger_cannot_be_silently_recreated_on_restart(self) -> None:
        self.path.unlink()
        with self.assertRaisesRegex(BudgetError, "restart cannot recreate"):
            BudgetLedger(self.path, SHA, LIMITS)

    def test_unknown_action_and_invalid_units_fail_closed(self) -> None:
        with self.assertRaisesRegex(BudgetError, "never reserved"):
            self.ledger.settle("unknown-001", units(model_calls=1))
        with self.assertRaisesRegex(BudgetError, "every"):
            self.ledger.reserve("ticket-001", "expansion", {"model_calls": 1})


if __name__ == "__main__":
    unittest.main()
