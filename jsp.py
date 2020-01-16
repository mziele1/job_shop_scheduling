import dwavebinarycsp
import itertools
from abc import ABC, abstractmethod
import pyqubo


class JSP(ABC):
    """
    A base class used to create JSPs
    Based on formulation in https://arxiv.org/pdf/1506.08479.pdf
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
                as by the end of time 7, it will still be executing. This parameter reduces size of the CSP and BQM.
        """
        self.job_dict = job_dict
        self.max_time = max_time if max_time is not None else self.calc_max_time()
        self.remove_impossible_times = remove_impossible_times

        self.time_vars = self.get_time_vars()

    @abstractmethod
    def add_start_once_constraints(self, start_times): pass

    @abstractmethod
    def add_machine_cap_constraints(self, machine_cap_pairs): pass

    @abstractmethod
    def add_precedence_constraints(self, precedence_pairs): pass

    def add_constraints(self):
        self.add_start_once_constraints(self.get_op_start_times())
        self.add_machine_cap_constraints(self.get_machine_cap_pairs())
        self.add_precedence_constraints(self.get_precedence_pairs())

    def get_op_start_times(self):
        """
        Return a list of tuples like (job, op_num, op_times) where op_times is a
        list of valid start times for the job-op_num combination.
        """
        for job, ops in self.time_vars.items():
            for op_num, op_times in enumerate(ops, start=1):
                yield(job, op_num, op_times)

    def get_machine_cap_pairs(self):
        """
        Create the set a_m: {(i, t, k, t') : (i, k) ∈ I_m × I_m, i != k, 0 ≤ t, t' ≤ T, 0 < t' − t < p_i}
                       b_m: {(i, t, k, t') : (i, k) ∈ I_m × I_m, i < k, t' = t, p_i > 0, p_j > 0}
                       for each machine
        NOTE: These pairs are variables for which concurrent execution would violate machine capacity
        """
        machines = set([
            op[0]
            for ops in self.job_dict.values()
            for op in ops
        ])

        r_m = {}
        for machine in machines:
            # create the base list of ops on m (one of I_m x I_m)
            ops_on_m = list([
                {"job": job, "op_idx": op_idx}
                for job, ops in self.job_dict.items()
                for op_idx, op in enumerate(ops)
                if (op[0] == machine)
            ])

            # a_m - list of machine usage schedules in which operation k starts BEFORE operation i finishes
            a_m = [
                (i, t, k, tprime)
                for i, k in itertools.product(ops_on_m, repeat=2)
                for t, tprime in itertools.product(self.time_vars[i["job"]][i["op_idx"]], self.time_vars[k["job"]][k["op_idx"]])
                if (i != k)
                and (t < tprime)
                and ((tprime - t) < self.job_dict[i["job"]][i["op_idx"]][1])
                and ((tprime - t) > 0)
            ]

            # b_m - list of machine usage schedules where two operations start at the same time and both of their
            #       processing times are nonzero
            b_m = [
                (i, t, k, tprime)
                for i, k in itertools.product(ops_on_m, repeat=2)
                for t, tprime in itertools.product(self.time_vars[i["job"]][i["op_idx"]], self.time_vars[k["job"]][k["op_idx"]])
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
            a_m_keys = [
                ((i["job"], i["op_idx"] + 1, t), (k["job"], k["op_idx"] + 1, tprime))
                for i, t, k, tprime in a_m
            ]
            b_m_keys = [
                ((i["job"], i["op_idx"] + 1, t), (k["job"], k["op_idx"] + 1, tprime))
                for i, t, k, tprime in b_m
            ]

            r_m[machine] = set(a_m_keys + b_m_keys)
        return r_m

    def get_precedence_pairs(self):
        """
        Return a list of pairs of time variables which cannot both be 1
        """
        precedence_list = {}
        for job, ops in self.job_dict.items():
            non_terminal_ops = list(range(len(ops) - 1))
            precedence_list[job] = [
                (i, t, i + 1, tprime) for i in non_terminal_ops
                for t, tprime in itertools.product(self.time_vars[job][i], self.time_vars[job][i + 1])
                if ((t + self.job_dict[job][i][1]) > tprime)
            ]
        return precedence_list

    def get_time_vars(self):
        """
        return a dict of valid starting times for each job's operations
        allow/remove invalid times with remove_impossible_times
        dict is like {job: {op_1: [times]...
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


class DBCJSP(JSP):
    """
    A class to create JSPs using DwaveBinaryCsp
    """
    def __init__(self, job_dict, max_time=None, remove_impossible_times=True):
        super().__init__(
            job_dict=job_dict,
            max_time=max_time,
            remove_impossible_times=remove_impossible_times)
        self.csp = dwavebinarycsp.ConstraintSatisfactionProblem(dwavebinarycsp.BINARY)

        self.add_constraints()

    def add_start_once_constraints(self, start_times):
        for job, op_num, op_times in start_times:
            constraint = dwavebinarycsp.Constraint.from_configurations(
                get_one_hot_configs(len(op_times)),
                ["x_{}_o{}_t{}".format(job, op_num, op_time) for op_time in op_times],
                vartype="BINARY",
                name="start_once"
            )
            self.csp.add_constraint(constraint)

    def add_machine_cap_constraints(self, machines):
        for machine_cap_pairs in machines.values():
            for i, k in machine_cap_pairs:
                constraint = dwavebinarycsp.Constraint.from_func(
                    one_at_a_time,
                    [
                        "x_{}_o{}_t{}".format(i[0], i[1], i[2]),
                        "x_{}_o{}_t{}".format(k[0], k[1], k[2])
                    ],
                    vartype="BINARY",
                    name="one_at_a_time"
                )
                self.csp.add_constraint(constraint)

    def add_precedence_constraints(self, precedence_pairs):
        for job, pairs in precedence_pairs.items():
            for i, t, k, tprime in pairs:
                constraint = dwavebinarycsp.Constraint.from_func(
                    enforce_precedence,
                    ["x_{}_o{}_t{}".format(job, i + 1, t), "x_{}_o{}_t{}".format(job, k + 1, tprime)],
                    vartype="BINARY",
                    name="enforce_precedence"
                )
                self.csp.add_constraint(constraint)


class PyQuboJSP(JSP):
    """
    Class to create JSPs using PyQUBO
    """
    def __init__(self, job_dict, max_time=None, remove_impossible_times=True):
        # time_vars are required by bin_vars, which must exist before add_constraints
        super().__init__(
            job_dict=job_dict,
            max_time=max_time,
            remove_impossible_times=remove_impossible_times)
        self.bin_vars = self.create_bin_vars()
        self.start_once_const = 0.0
        self.machine_cap_const = 0.0
        self.operation_order_const = 0.0

        self.add_constraints()

        self.penalty_strength = pyqubo.Placeholder("penalty_strength")
        self.hamiltonian = 0.0 \
                           + self.penalty_strength \
                           * (self.start_once_const
                              + self.machine_cap_const
                              + self.operation_order_const)

    def create_bin_vars(self):
        bin_vars = {}
        for job, ops in self.time_vars.items():
            bin_vars[job] = {}
            for op_num, op_times in enumerate(ops, start=1):
                bin_vars[job][op_num] = {}
                for op_time in op_times:
                    bin_vars[job][op_num][op_time] = pyqubo.Binary("x_{}_o{}_t{}".format(job, op_num, op_time))
        return bin_vars

    def add_start_once_constraints(self, start_times):
        for job, op_num, op_times in start_times:
            # constraint is (sum(time_vars) - 1)**2; penalizes more or less than one start time
            self.start_once_const += \
                pyqubo.Constraint(
                    (
                        pyqubo.Sum(
                            0,
                            len(op_times),
                            lambda t: self.bin_vars[job][op_num][op_times[t]]
                        ) - 1
                    ) ** 2,
                    "start_once_{}_o{}".format(job, op_num)
                )

    def add_machine_cap_constraints(self, machines):
        for machine_cap_pairs in machines.values():
            for i, k in machine_cap_pairs:
                self.machine_cap_const += \
                    pyqubo.Constraint(
                        self.bin_vars[i[0]][i[1]][i[2]] * self.bin_vars[k[0]][k[1]][k[2]],
                        "machine_cap__{}_{}_{}__{}_{}_{}".format(i[0], i[1], i[2], k[0], k[1], k[2])
                    )

    def add_precedence_constraints(self, precedence_pairs):
        for job, pairs in precedence_pairs.items():
            for i, t, k, tprime in pairs:
                self.operation_order_const += \
                    pyqubo.Constraint(
                        self.bin_vars[job][i + 1][t] * self.bin_vars[job][k + 1][tprime],
                        "operation_order__{}_{}_{}__{}_{}_{}".format(job, i + 1, t, job, k + 1, tprime)
                    )


def start_once(*args):
    # this function represents the constraint that each operation must start exactly once
    # input is the list of x_i_t for a single operations for each possible time (t <= t_max)
    # x_i_t == 1 if operation i starts at time t, else 0
    # sum(xi) must == 1
    return sum(args) == 1


def get_one_hot_configs(length):
    # this function returns the list of all one-hot configurations with the specified length
    # compared to the start_once function, this function runs much quicker when using csp.add_constraint
    #   as the valid configurations are provided, rather than an evaluating function that will be called
    #   on all 2^n configurations
    configs = []
    for i in range(length):
        config = [0] * length
        config[i] = 1
        configs.append(tuple(config))
    return configs


def one_at_a_time(x_i_t, x_k_tprime):
    # this function ensures that the two input start times are NOT both 1
    # input is a pair of operation starting times that would violate the one operation per machine at a time constraint
    # x_i_t * x_k_tprime must not be 1
    return (x_i_t * x_k_tprime) == 0


def enforce_precedence(x_i_t, x_k_tprime):
    # this function penalizes schedules where the successor to operation i (k) cannot start before i has finished
    # input will be two start times where x_k_tprime must == 0, else it starts before its preceding operation finishes
    return (x_i_t * x_k_tprime) == 0
