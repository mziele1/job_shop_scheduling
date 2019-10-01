import unittest
import jsp as jsp_mod


class TestConstraints(unittest.TestCase):
    def test_start_once(self):
        invalid_configs = [[0], [0, 0], [1, 1]]
        for config in invalid_configs:
            self.assertFalse(jsp_mod.start_once(*config))

        valid_configs = [[1], [1, 0], [0, 0, 1]]
        for config in valid_configs:
            self.assertTrue(jsp_mod.start_once(*config))

    def test_one_at_a_time(self):
        invalid_configs = [[1, 1]]
        for config in invalid_configs:
            self.assertFalse(jsp_mod.one_at_a_time(*config))

        valid_configs = [[1, 0], [0, 1], [0, 0]]
        for config in valid_configs:
            self.assertTrue(jsp_mod.one_at_a_time(*config))

    def test_enforce_precedence(self):
        invalid_configs = [[1, 1]]
        for config in invalid_configs:
            self.assertFalse(jsp_mod.enforce_precedence(*config))

        valid_configs = [[1, 0], [0, 1], [0, 0]]
        for config in valid_configs:
            self.assertTrue(jsp_mod.enforce_precedence(*config))
