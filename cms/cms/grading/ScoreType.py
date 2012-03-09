#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import simplejson as json

from cms import logger


class ScoreTypes:
    """Contain constants for all defined score types.

    """
    # TODO: if we really want to do plugins, this class should look up
    # score types in some given path.

    # The evaluation is the sum of the outcome for all testcases.
    SCORE_TYPE_SUM = "ScoreTypeSum"

    # The evaluation is the sum over some specified ranges of the
    # minimum outcome amongst the testcases in that range.
    SCORE_TYPE_GROUP_MIN = "ScoreTypeGroupMin"

    # The same, with average substituting minimum.
    SCORE_TYPE_GROUP_AVG = "ScoreTypeGroupAvg"

    # The same, with multiplication substituting minimum.
    SCORE_TYPE_GROUP_MUL = "ScoreTypeGroupMul"

    # The evaluation is the sum over all testcases of the ratio
    # between the outcome and the maximum amongst all outcomes for
    # that testcase and a given value.
    SCORE_TYPE_RELATIVE = "ScoreTypeRelative"

    @staticmethod
    def get_score_type(submission=None, task=None, score_type=None):
        """Returns the right score type class for a given string,
        provided in one out of the three possible way (submission,
        task or score_type).

        submission (Submission): the submission that needs the score
                                 type.
        task (Task): the task that needs the score type.
        score_type_name (string): the name of the desired score_type.

        return (object): an instance of the correct ScoreType class.

        """
        # Validate arguments.
        if [x is not None
            for x in [submission, task, score_type]].count(True) != 1:
            raise ValueError("Need at most one way to get the score type.")

        # Recover information from the arguments.
        score_parameters = None
        public_testcases = None
        if submission is not None:
            task = submission.task
        if task is not None:
            score_type = task.score_type
            score_parameters = json.loads(task.score_parameters)
            public_testcases = [testcase.public
                                for testcase in task.testcases]

        if score_type == ScoreTypes.SCORE_TYPE_SUM:
            return ScoreTypeSum(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MIN:
            return ScoreTypeGroupMin(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_AVG:
            return ScoreTypeGroupAvg(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MUL:
            return ScoreTypeGroupMul(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_RELATIVE:
            return ScoreTypeRelative(score_parameters, public_testcases)
        else:
            raise KeyError


class ScoreType:
    """Base class for all score types, that must implement all methods
    defined here.

    """
    def __init__(self, parameters, public_testcases):
        """Initializer.

        parameters (object): format is specified in the subclasses.
        public_testcases (list): list of booleans indicating if the
                                 testcases are pulic or not
        """
        self.parameters = parameters
        self.public_testcases = public_testcases

        # Dict that associate to a username the list of its
        # submission_ids - sorted by timestamp.
        self.submissions = {}

        # Dict that associate to every submission_id its data:
        # timestamp, username, evaluations, tokened, score.
        self.pool = {}

        # Dict that associate to a username the maximum score amongst
        # its tokened submissions and the last one.
        self.scores = {}

        # Preload the maximum possible scores.
        self.max_score, self.max_public_score = self.max_scores()

        # Initialization method that can be overwritten by subclass.
        self.initialize()

    def initialize(self):
        """Intended to be overwritten by subclasses.

        """
        pass

    def add_submission(self, submission_id, timestamp, username,
                       evaluations, tokened):
        """To call in order to add a submission to the computation of
        all scores.

        submission_id (int): id of the new submission.
        timestamp (int): time of submission.
        username (string): username of the owner of the submission.
        evaluations (list): list of objects representing the evaluations.
        tokened (bool): if the user played a token on submission.

        """
        self.pool[submission_id] = {
            "timestamp": timestamp,
            "username": username,
            "evaluations": evaluations,
            "tokened": tokened,
            "score": None,
            "details": None,
            "public_score": None,
            "public_details": None
            }
        (score, details, public_score, public_details) = \
                self.compute_score(submission_id)
        self.pool[submission_id]["score"] = score
        self.pool[submission_id]["details"] = details
        self.pool[submission_id]["public_score"] = public_score
        self.pool[submission_id]["public_details"] = public_details

        if username not in self.submissions or \
            self.submissions[username] is None:
            self.submissions[username] = [submission_id]
        else:
            self.submissions[username].append(submission_id)

        # We expect submissions to arrive more or less in the right
        # order, so we insert-sort the new one.
        i = len(self.submissions[username]) - 1
        while i > 0 and \
            self.pool[self.submissions[username][i - 1]]["timestamp"] > \
            self.pool[self.submissions[username][i]]["timestamp"]:
            self.submissions[username][i - 1], \
                self.submissions[username][i] = \
                self.submissions[username][i], \
                self.submissions[username][i - 1]
            i -= 1

        self.update_scores(submission_id)

    def add_token(self, submission_id):
        """To call when a token is played, so that the scores updates.

        submission_id (int): id of the tokened submission.

        """
        try:
            self.pool[submission_id]["tokened"] = True
        except KeyError:
            logger.error("Submission %d not found in ScoreType's pool." %
                         submission_id)

        self.update_scores(submission_id)

    def compute_all_scores(self):
        """Recompute all scores, usually needed only in case of
        problems.

        """
        for submissions in self.submissions.itervalues():
            # We recompute score for all submissions of user...
            for submission_id in submissions:
                self.compute_score(submission_id)
            # and update the score of the user (only once).
            if submissions != []:
                self.update_scores(submissions[-1])

    def update_scores(self, new_submission_id):
        """Update the scores of the users assuming that only this
        submission appeared or was modified (i.e., tokened). The way
        to do this depends on the subclass, so we leave this
        unimplemented.

        new_submission_id (int): id of the newly added submission.

        """
        logger.error("Unimplemented method update_scores.")
        raise NotImplementedError

    def max_scores(self):
        """Returns the maximum score that one could aim to in this
        problem. Also return the maximum score from the point of view
        of a user that did not play the token. Depend on the subclass.

        return (float, float): maximum score and maximum score with
                               only public testcases.

        """
        logger.error("Unimplemented method max_scores.")
        raise NotImplementedError

    def compute_score(self, submission_id):
        """Computes a score of a single submission. We don't know here
        how to do it, but our subclasses will.

        submission_id (int): the submission to evaluate.

        returns (float, list, float, list): respectively: the score,
                                            the list of additional
                                            information (e.g.
                                            subtasks' score), and the
                                            same information from the
                                            point of view of a user
                                            that did not play a token.

        """
        logger.error("Unimplemented method compute_score.")
        raise NotImplementedError


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission and max_scores.

    """
    def update_scores(self, new_submission_id):
        """Update the scores of the user assuming that only this
        submission appeared.

        new_submission_id (int): id of the newly added submission.

        """
        username = self.pool[new_submission_id]["username"]
        submission_ids = self.submissions[username]
        score = 0.0

        # We find the best amongst all tokened submissions...
        for submission_id in submission_ids:
            if self.pool[submission_id]["tokened"]:
                score = max(score, self.pool[submission_id]["score"])
        # and the last one.
        if submission_ids != []:
            score = max(score, self.pool[submission_ids[-1]]["score"])

        # Finally we update the score table.
        self.scores[username] = score


class ScoreTypeSum(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes,
    multiplied by the integer parameter.

    """
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases:
            if public:
                public_score += self.parameters
            score += self.parameters
        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        public_score = 0.0
        score = 0.0
        for evaluation, public in zip(evaluations, self.public_testcases):
            if public:
                public_score += evaluation
            score += evaluation
        return round(score * self.parameters, 2), None, \
               round(public_score * self.parameters, 2), None

class ScoreTypeSubtaskGroups(ScoreTypeAlone):
    """This scoring method uses groups of sub-tasks which can be composed of
    any subset of test cases. Each group has a name and a weight. The actual
    method of calculating the score for a group is defined by a derived class
    (this class is abstract).

    Score parameters are: [
        ["subtask 1 name", weight, [testcase1, testcase2, ...]],
        ["subtask 2 name", weight, [testcase1, testcase2, ...]],
        ...
    ]

    A group with a weight of 0 will not contribute towards the score, but will
    display with a simple PASS/FAIL indicator to the contestant. This is useful
    for sample cases.
    """

    def _compute_group_score(self, score_array):
        """Given the individual test case results in score_array, this function
        should return the value which the group's weight will be multiplied by
        to obtain the final score for the group."""
        raise NotImplementedError

    def max_scores(self):
        """Compute the maximum score of a submission.
        FIXME: this suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.
        """
        public_score = 0.0
        score = 0.0
        num_total_cases = len(self.public_testcases)
        for group in self.parameters:
            _, max_score, cases = group
            # Check all the cases are valid.
            usable_cases = [x for x in cases if 0 <= x < num_total_cases]
            if len(usable_cases) != len(cases):
                logger.error("Task has invalid parameters (invalid cases)")
            cases = usable_cases

            if len(cases) == 0:
                logger.error("Task has invalid parameters (empty case-list)")
                # Technically it's undefined. We don't give the marks for an
                # empty case list.
                continue

            # Are all the testcases in this group public?
            public = all([self.public_testcases[x] for x in cases])

            score += max_score
            if public:
                public_score += max_score

        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        scores = []
        max_scores = []
        public_scores = []
        max_public_scores = []
        public_index = []
        num_total_cases = len(self.public_testcases)
        details = []
        public_details = []
        for group in self.parameters:
            name, max_score, cases = group
            cases = [x for x in cases if 0 <= x < num_total_cases]
            if len(cases) == 0:
                continue

            # Are all the testcases in this group public?
            public = all([self.public_testcases[x] for x in cases])

            multiplier = self._compute_group_score([evaluations[x] for x in cases])
            score = multiplier * max_score
            if max_score == 0:
                if int(round(multiplier)) == 1:
                    result_str = "PASS"
                else:
                    result_str = "FAIL"
            else:
                result_str = "%lg" % score

            detail_str = "%s: %s" % (name, result_str)

            scores.append(score)
            max_scores.append(max_score)
            details.append(detail_str)
            if public:
                public_scores.append(score)
                max_public_scores.append(max_score)
                public_index.append(len(scores) - 1)
                public_details.append(detail_str)

        total_score = sum(scores)
        total_public_score = sum(public_scores)
        return round(total_score, 2), details, \
               round(total_public_score, 2), public_details

class ScoreTypeGroupMin(ScoreTypeSubtaskGroups):
    """A subtask-group-scored scheme, using the minimum score within each group.

    See ScoreTypeSubtaskGroups for details.
    """
    def _compute_group_score(self, score_array):
        return min(score_array)

class ScoreTypeGroupAvg(ScoreTypeSubtaskGroups):
    """A subtask-group-scored scheme, using the unweighted average score within
    each group.

    See ScoreTypeSubtaskGroups for details.
    """
    def _compute_group_score(self, score_array):
        return 1.0 * sum(score_array) / len(score_array)

class ScoreTypeGroupMul(ScoreTypeSubtaskGroups):
    """A subtask-group-scored scheme, using the product of the scores within
    each group.

    See ScoreTypeSubtaskGroups for details.
    """
    def _compute_group_score(self, score_array):
        return reduce(lambda x, y: x * y, score_array)

class ScoreTypeRelative(ScoreType):
    """Scoring systems where the score of a submission is the sum of
    the scores for each testcase, and the score of a testcase is the
    ratio between the outcome of that testcase and the best outcome of
    all others submissions (also in the future) that are going to
    contribute to the final score (i.e., the last submission for all
    users, and the submissions where the user used a token). Also
    compared with a 'basic' outcome given as a parameter. Finally, the
    score is multiplied by a multiplier given as parameter.

    """
    def initialize(self):
        """Init.

        parameters (couple): the first element is a float, the
                             multiplier; the second is a list of
                             length eval_num, whose elements are the
                             'basic' outcomes, or None for no basic
                             outcome.

        """
        # We keep the best outcome that is gonna stay (i.e., not
        # amongst the last submissions, but only tokened and basic
        # outcomes. Elements may be None.
        self.best_tokenized_outcomes = []
        for par in self.parameters[1]:
            self.best_tokenized_outcomes.append(par)

        # Temporary store the best outcomes for every evaluation as
        # computed in compute_score, to use them in update_scores.
        self.best_outcomes = None

    def compute_best_outcomes(self):
        """Merge best_tokenized_outcomes with the last submissions of
        every user to return the current best outcome for every
        evaluation.

        returns (list): a list of one float for every evaluation, the
                        best outcome.

        """
        best_outcomes = self.best_tokenized_outcomes[:]
        for username in self.submissions:
            submissions = self.submissions[username]
            if submissions == []:
                continue
            for i, outcome in \
                enumerate(self.pool[submissions[-1]]["evaluations"]):
                best_outcomes[i] = max(best_outcomes[i], outcome)

        return best_outcomes

    def update_scores(self, new_submission_id):
        """Update the scores of the contest assuming that only this
        submission appeared.

        new_submission_id (int): id of the newly added submission.

        best_outcomes (list):

        """
        # If we just computed best_outcomes in compute_score, we don't
        # compute it again.
        if self.best_outcomes is None:
            best_outcomes = self.compute_best_outcomes()
        else:
            best_outcomes = self.best_outcomes
            self.best_outcomes = None

        # Then, we update the score for each submission, and we update
        # the users' scores.
        for username in self.submissions:
            submissions = self.submissions[username]
            score = 0.0
            for submission_id in submissions:
                self.pool[submission_id]["score"] = \
                    sum([float(x) / y for x, y
                         in zip(self.pool[submission_id]["evaluations"],
                                best_outcomes)]) * self.parameters[0]
                if self.pool[submission_id]["tokened"] is not None:
                    score = max(score, self.pool[submission_id]["score"])
            if submissions != []:
                score = max(score, self.pool[submissions[-1]]["score"])
            self.scores[username] = score

    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases:
            score += self.parameters[0]
            if public:
                public_score += self.parameters[0]
        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        self.best_outcomes = self.compute_best_outcomes()
        score = 0.0
        public_score = 0.0
        for public, evaluation, best in zip(
            self.public_testcases,
            self.pool[submission_id]["evaluations"],
            self.best_outcomes):
            to_add = float(evaluation) / best * self.parameters[0]
            score += to_add
            if public:
                public_score += to_add
        return round(score, 2), None, round(public_score, 2), None
