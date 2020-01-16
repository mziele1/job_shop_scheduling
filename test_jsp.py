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

    def test_get_one_hot_configs(self):
        lengths = [1, 2, 7]
        for length in lengths:
            configs = jsp_mod.get_one_hot_configs(length)
            for config in configs:
                self.assertEqual(sum(config), 1)


class TestCSP(unittest.TestCase):
    def test_simple_jsp(self):
        jobs = {
            "j1": [("m1", 2), ("m2", 1), ("m3", 1)],
            "j2": [("m3", 2), ("m1", 1), ("m2", 2)],
            "j3": [("m2", 1), ("m1", 1), ("m3", 2)]
        }
        max_time = 7

        jsp = jsp_mod.DBCJSP(jobs, max_time, True)
        csp = jsp.csp

        valid_schedules = [{
            'x_j1_o1_t1': 0, 'x_j1_o1_t2': 1, 'x_j1_o1_t3': 0, 'x_j1_o1_t4': 0,
            'x_j1_o2_t3': 0, 'x_j1_o2_t4': 0, 'x_j1_o2_t5': 1, 'x_j1_o2_t6': 0,
            'x_j1_o3_t4': 0, 'x_j1_o3_t5': 0, 'x_j1_o3_t6': 0, 'x_j1_o3_t7': 1,
            'x_j2_o1_t1': 1, 'x_j2_o1_t2': 0, 'x_j2_o1_t3': 0,
            'x_j2_o2_t3': 0, 'x_j2_o2_t4': 0, 'x_j2_o2_t5': 1,
            'x_j2_o3_t4': 0, 'x_j2_o3_t5': 0, 'x_j2_o3_t6': 1,
            'x_j3_o1_t1': 0, 'x_j3_o1_t2': 0, 'x_j3_o1_t3': 1, 'x_j3_o1_t4': 0,
            'x_j3_o2_t2': 0, 'x_j3_o2_t3': 0, 'x_j3_o2_t4': 1, 'x_j3_o2_t5': 0,
            'x_j3_o3_t3': 0, 'x_j3_o3_t4': 0, 'x_j3_o3_t5': 1, 'x_j3_o3_t6': 0
            }, {
            'x_j1_o1_t1': 1, 'x_j1_o1_t2': 0, 'x_j1_o1_t3': 0, 'x_j1_o1_t4': 0,
            'x_j1_o2_t3': 1, 'x_j1_o2_t4': 0, 'x_j1_o2_t5': 0, 'x_j1_o2_t6': 0,
            'x_j1_o3_t4': 0, 'x_j1_o3_t5': 0, 'x_j1_o3_t6': 0, 'x_j1_o3_t7': 1,
            'x_j2_o1_t1': 0, 'x_j2_o1_t2': 0, 'x_j2_o1_t3': 1,
            'x_j2_o2_t3': 0, 'x_j2_o2_t4': 0, 'x_j2_o2_t5': 1,
            'x_j2_o3_t4': 0, 'x_j2_o3_t5': 0, 'x_j2_o3_t6': 1,
            'x_j3_o1_t1': 1, 'x_j3_o1_t2': 0, 'x_j3_o1_t3': 0, 'x_j3_o1_t4': 0,
            'x_j3_o2_t2': 0, 'x_j3_o2_t3': 0, 'x_j3_o2_t4': 1, 'x_j3_o2_t5': 0,
            'x_j3_o3_t3': 0, 'x_j3_o3_t4': 0, 'x_j3_o3_t5': 1, 'x_j3_o3_t6': 0
        }]
        for schedule in valid_schedules:
            self.assertTrue(csp.check(schedule))

        invalid_schedules = [{
            'x_j1_o1_t1': 0, 'x_j1_o1_t2': 1, 'x_j1_o1_t3': 0, 'x_j1_o1_t4': 1,
            'x_j1_o2_t3': 0, 'x_j1_o2_t4': 0, 'x_j1_o2_t5': 1, 'x_j1_o2_t6': 0,
            'x_j1_o3_t4': 0, 'x_j1_o3_t5': 0, 'x_j1_o3_t6': 0, 'x_j1_o3_t7': 1,
            'x_j2_o1_t1': 1, 'x_j2_o1_t2': 0, 'x_j2_o1_t3': 0,
            'x_j2_o2_t3': 0, 'x_j2_o2_t4': 0, 'x_j2_o2_t5': 1,
            'x_j2_o3_t4': 0, 'x_j2_o3_t5': 0, 'x_j2_o3_t6': 1,
            'x_j3_o1_t1': 0, 'x_j3_o1_t2': 0, 'x_j3_o1_t3': 1, 'x_j3_o1_t4': 0,
            'x_j3_o2_t2': 0, 'x_j3_o2_t3': 0, 'x_j3_o2_t4': 1, 'x_j3_o2_t5': 0,
            'x_j3_o3_t3': 0, 'x_j3_o3_t4': 0, 'x_j3_o3_t5': 1, 'x_j3_o3_t6': 0
            }, {
            'x_j1_o1_t1': 0, 'x_j1_o1_t2': 0, 'x_j1_o1_t3': 0, 'x_j1_o1_t4': 1,
            'x_j1_o2_t3': 1, 'x_j1_o2_t4': 0, 'x_j1_o2_t5': 0, 'x_j1_o2_t6': 0,
            'x_j1_o3_t4': 0, 'x_j1_o3_t5': 0, 'x_j1_o3_t6': 0, 'x_j1_o3_t7': 1,
            'x_j2_o1_t1': 0, 'x_j2_o1_t2': 0, 'x_j2_o1_t3': 1,
            'x_j2_o2_t3': 0, 'x_j2_o2_t4': 0, 'x_j2_o2_t5': 1,
            'x_j2_o3_t4': 0, 'x_j2_o3_t5': 0, 'x_j2_o3_t6': 1,
            'x_j3_o1_t1': 1, 'x_j3_o1_t2': 0, 'x_j3_o1_t3': 0, 'x_j3_o1_t4': 0,
            'x_j3_o2_t2': 0, 'x_j3_o2_t3': 0, 'x_j3_o2_t4': 1, 'x_j3_o2_t5': 0,
            'x_j3_o3_t3': 0, 'x_j3_o3_t4': 0, 'x_j3_o3_t5': 1, 'x_j3_o3_t6': 0
        }]
        for schedule in invalid_schedules:
            self.assertFalse(csp.check(schedule))
