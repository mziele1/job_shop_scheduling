import dwavebinarycsp
import itertools


def start_once(*args):
    # this function represents the constraint that each operation must start exactly once
    # input is the list of x_i_t for a single operations for each possible time (t <= t_max)
    # x_i_t == 1 if operation i starts at time t, else 0
    # sum(xi) must == 1
    return sum(args) == 1


def one_at_a_time(x_i_t, x_k_tprime):
    # this function ensures that the two input start times are NOT both 1
    # input is a pair of operation starting times that would violate the one operation per machine at a time constraint
    # x_i_t * x_k_tprime must not be 1
    return (x_i_t * x_k_tprime) == 0


def enforce_precedence(x_i_t, x_k_tprime):
    # this function penalizes schedules where the successor to operation i (k) cannot start before i has finished
    # input will be two start times where x_k_tprime must == 0, else it starts before its preceding operation finishes
    return (x_i_t * x_k_tprime) == 0


class JobShopScheduler:
    """
    Implementation of the JSP described in https://arxiv.org/pdf/1506.08479.pdf
    """

    def __init__(self, job_dict, max_time=None, remove_impossible_times=True):
        """
        Args:
            job_dict: A dict of job (string) to operation lists. An operation list is an ordered list of tuples, each
                representing one operation and containing machine (string) and processing time (int).
                E.g. {
                        "j1": [("m1", 2), ("m2", 1), ("m3", 1)],
                        "j2": [("m3", 2), ("m1", 1), ("m2", 2)],
                        "j3": [("m2", 1), ("m1", 1), ("m3", 2)]
                     }
            max_time: The max allowed time for a schedule.
            remove_impossible_times: Whether or not to remove (by never creating, as opposed to variable fixing)
                impossible start/end times for a variable, considering other operations in the same job. E.g. if
                job1 op1 has p=2, and max_time=7, any schedule where it starts executing in time 7 will be invalid,
                s by the end of time 7, it will still be executing. This parameter reduces the number of variables
                (and by extension, constraints).
        """
        self.job_dict = job_dict
        self.max_time = max_time if max_time != None else self.calc_max_time()
        self.remove_impossible_times = remove_impossible_times
        self.csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.BINARY)
        self.add_constraints()

    def add_constraints(self):
        # Add constraints to the CSP, which also creates the variables
        # times: the formulation has (0 ≤ t, t' ≤ T) but the figures seem to go by (1 ≤ t, t' ≤ T) I will use the
        # latter as it makes more sense (especially regarding T)
        job_times_dict = self.get_times()

        # Constraint 1: start once
        for job, ops in job_times_dict.items():
            for op_num, op_times in enumerate(ops, start=1):
                self.csp.add_constraint(start_once, ["x_{}_o{}_t{}".format(job, op_num, op_time) for op_time in op_times])

        # Constraint 2: machine can only execute one operation per time
        machines = set([op[0] for ops in self.job_dict.values()
                              for op in ops])
        for machine in machines:
            # create the set a_m: {(i, t, k, t') : (i, k) ∈ I_m × I_m, i != k, 0 ≤ t, t' ≤ T, 0 < t' − t < p_i}
            #                b_m: {(i, t, k, t') : (i, k) ∈ I_m × I_m, i < k, t' = t, p_i > 0, p_j > 0}
            # NOTE: this creates lists of INVALID configuration, and the one_at_a_time constraint ensures that the
            #       invalid configuration never occurs (x_i_t * x_k_tprime) == 0
            # create the base list of ops on m (one of I_m x I_m)
            ops_on_m = list([{"job": job, "op_idx": op_idx} for job, ops in self.job_dict.items()
                                                            for op_idx, op in enumerate(ops)
                                                            if (op[0] == machine)])
            # a_m - list of machine usage schedules in which operation k starts BEFORE operation i finishes
            a_m = [(i, t, k, tprime) for i, k in itertools.product(ops_on_m, repeat=2)
                                     for t, tprime in itertools.product(job_times_dict[i["job"]][i["op_idx"]], job_times_dict[k["job"]][k["op_idx"]])
                                        if (i != k)
                                        and (t < tprime)
                                        and ((tprime - t) < self.job_dict[i["job"]][i["op_idx"]][1])
                                        and ((tprime - t) > 0)
            ]
            # b_m - list of machine usage schedules where two operations start at the same time and both of their
            #       processing times are nonzero
            b_m = [(i, t, k, tprime) for i, k in itertools.product(ops_on_m, repeat=2)
                                     for t, tprime in itertools.product(job_times_dict[i["job"]][i["op_idx"]], job_times_dict[k["job"]][k["op_idx"]])
                                        # for (i < k), we just need to pick one "side", the order of i,k doesn't really
                                        # matter since they are at the same time (t == tprime)
                                        #if i < k
                                        if ((i["job"] < k["job"]) or
                                            ((i["job"] == k["job"]) and (i["op_idx"] < k["op_idx"])))
                                        and (t == tprime)
                                        and (self.job_dict[i["job"]][i["op_idx"]][1] > 0)
                                        and (self.job_dict[k["job"]][k["op_idx"]][1] > 0)
            ]
            # convert to time variables
            a_m_time_vars = [("x_{}_o{}_t{}".format(i["job"], i["op_idx"] + 1, t), "x_{}_o{}_t{}".format(k["job"], k["op_idx"] + 1, tprime))
                                for i, t, k, tprime in a_m
            ]
            b_m_time_vars = [("x_{}_o{}_t{}".format(i["job"], i["op_idx"] + 1, t), "x_{}_o{}_t{}".format(k["job"], k["op_idx"] + 1, tprime))
                                for i, t, k, tprime in b_m
            ]
            r_m = set(a_m_time_vars + b_m_time_vars)
            for pair in r_m:
                self.csp.add_constraint(one_at_a_time, [pair[0], pair[1]])

        # Constraint 3, operation precedence
        for job, ops in self.job_dict.items():
            non_terminal_ops = list(range(len(ops) - 1))
            precedence_list = [(i, t, i + 1, tprime) for i in non_terminal_ops
                                                     for t, tprime in itertools.product(job_times_dict[job][i], job_times_dict[job][i + 1])
                                                     if ((t + self.job_dict[job][i][1]) > tprime)
            ]
            for i, t, k, tprime in precedence_list:
                self.csp.add_constraint(enforce_precedence, ["x_{}_o{}_t{}".format(job, i + 1, t), "x_{}_o{}_t{}".format(job, k + 1, tprime)])

    def get_times(self):
        """
        return a dict of valid starting times for each job's operations
        allow/remove invalid times with remove_impossible_times
        """
        times_dict = {}
        for job, ops in self.job_dict.items():
            times_dict[job] = []
            # account for current and future operations' processing time, -1 to allow processing in last slot
            if self.remove_impossible_times == True:
                forward_space = sum([op[1] for op in ops]) - 1
            else:
                forward_space = 0
            # account for sum of previous operations' processing times
            back_space = 0
            for job_num, op in enumerate(ops, start=1):
                start = back_space
                end = self.max_time - forward_space
                # +1 to adjust to 1 based indexing
                times_dict[job].append([t + 1 for t in range(start, end)])
                if self.remove_impossible_times == True:
                    forward_space -= op[1]
                    back_space += op[1]
        return times_dict

    def calc_max_time(self):
        # use sum of times as max_time if not supplied
        sum_times = 0
        for job, ops in self.job_dict.items():
            for op in ops:
                sum_times += op[1]
        return sum_times
