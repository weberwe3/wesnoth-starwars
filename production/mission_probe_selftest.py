"""Regression checks for installed-engine verdict integrity."""

import unittest

from mission_probe import _meets_expectation


class MissionProbeVerdictTests(unittest.TestCase):
    def test_victory_requires_all_assertions_to_hold(self) -> None:
        self.assertTrue(_meets_expectation("path_to_beacon", "victory", 8,
                                           "PASS TEST (VICTORY) (8): fixture"))
        self.assertFalse(_meets_expectation(
            "path_to_beacon", "victory", 8,
            "conditional test unexpectedly failed\nPASS TEST (VICTORY) (8): fixture"))

    def test_intentional_negative_still_requires_its_failed_assertion(self) -> None:
        self.assertTrue(_meets_expectation("first_move_origin", "fail", 1,
                                           "conditional test unexpectedly failed"))
        self.assertFalse(_meets_expectation("first_move_origin", "fail", 1,
                                            "FAIL TEST without a conditional failure"))

    def test_player_command_error_never_qualifies(self) -> None:
        self.assertFalse(_meets_expectation("path_to_beacon", "victory", 8,
                                            "Error via [do_command]\nPASS TEST (VICTORY) (8)"))


if __name__ == "__main__":
    unittest.main()
