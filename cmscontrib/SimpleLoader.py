#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import io
import json
import logging
import os
import os.path
import sys
import yaml
from datetime import timedelta

from cms import LANGUAGES
from cmscommon.datetime import make_datetime
from cms.db import Contest, User, Task, Statement, Attachment, \
    SubmissionFormatElement, Dataset, Manager, Testcase
from cmscontrib.BaseLoader import Loader
from cmscontrib import touch


logger = logging.getLogger(__name__)


# Patch PyYAML to make it load all strings as unicode instead of str
# (see http://stackoverflow.com/questions/2890146).
def construct_yaml_str(self, node):
    return self.construct_scalar(node)
yaml.Loader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)
yaml.SafeLoader.add_constructor("tag:yaml.org,2002:str", construct_yaml_str)

def rebuild_list(old):
    l = []
    if old is None:
        return l
    for s in old:
        numbers = str(s).strip().split('-')
        if len(numbers) == 1:
            l.append("%03d" % int(numbers[0]))
        else:
            for i in xrange(int(numbers[0]), int(numbers[1]) + 1):
                l.append("%03d" % i)
    return l

class SimpleLoader(Loader):
    """Support all contests formats.

    """

    short_name = 'simple'
    description = 'Simple format'

    @classmethod
    def detect(cls, path):
        """See docstring in class Loader.

        """
        return False

    def get_contest(self):
        """See docstring in class Loader.

        """

        args = {}

        name = os.path.split(self.path)[1]
        args["description"] = args["name"] = name
        args["token_mode"] = "disabled"
        self.token_mode = {"token_mode": "disabled"}
        args["start"] = make_datetime(1388534400) # Beginning of 2014 year
        args["stop"] = make_datetime(1577836800) # Beginning of 2020 year
        args["per_user_time"] = timedelta(seconds=18000) # 5 hours

        # Loading tasks
        tasks = []
        for task in os.listdir(self.path):
            if os.path.isdir(os.path.join(self.path, task)):
                logger.info("Task %s found" % task)
                tasks.append(task)

        users = []

        self.timedelta_params = ["token_min_interval", "token_gen_interval",
            "min_submission_interval", "min_user_test_interval", "per_user_time"]
        if os.path.isfile(os.path.join(self.path, "contest.yaml")):
            conf = yaml.safe_load(io.open(os.path.join(self.path, "contest.yaml"), "rt", encoding="utf-8"))
            logger.info("Loading YAML-encoded parameters for contest %s." % name)
            for key, param in conf.iteritems():
                if key == "users":
                    logger.info("User list found")
                    self.users_conf = dict((user['username'], user)
                                           for user in param)
                    users = self.users_conf.keys()
                elif key == "start" or key == "stop":
                    args[key] = make_datetime(param)
                elif key in self.timedelta_params:
                    args[key] = timedelta(seconds=param)
                elif key == "tasks":
                    # To prevent task order
                    logger.info("Task list found, overwrite existing")
                    tasks = param
                elif key.startswith("token"):
                    if key != "tokens_are_global":
                        if conf.get("tokens_are_global", False):
                            args[key] = param
                            self.token_mode["token_mode"] = "infinite"
                        else:
                            args["token_mode"] = "infinite"
                            self.token_mode[key] = param
                else:
                    args[key] = param
        self.tasks_order = dict((name, num)
                                for num, name in enumerate(tasks))

        logger.info("Contest parameters loaded.")
        return Contest(**args), tasks, users

    def has_changed(self, name):
        """See docstring in class Loader

        """
        return True

    def get_user(self, username):
        """See docstring in class Loader.

        """
        logger.info("Loading parameters for user %s." % username)
        conf = self.users_conf[username]
        assert username == conf['username']

        args = conf
        if "first_name" not in args:
            args["first_name"] = ""
        if "last_name" not in args:
            args["last_name"] = args["username"]
        if "hidden" not in args:
            args["hidden"] = False
        
        logger.info("User parameters loaded.")

        return User(**args)

    def get_task(self, name):
        """See docstring in class Loader.

        """
        try:
            num = self.tasks_order[name]
        # Here we expose an undocumented behavior, so that cmsMake can
        # import a task even without the whole contest; this is not to
        # be relied upon in general
        except AttributeError:
            num = 1

        task_path = os.path.join(self.path, name)
        conf = {}
        try:
            conf = yaml.safe_load(
                io.open(os.path.join(task_path, "task.yaml"),
                        "rt", encoding="utf-8"))
        except IOError:
            if os.path.exists(os.path.join(task_path, name + ".yaml")):
                conf = yaml.safe_load(
                    io.open(os.path.join(task_path, name + ".yaml"),
                            "rt", encoding="utf-8"))
        args = {}

        args["num"] = num
        args["name"] = name
        args["title"] = name.title()
        primary_language = conf.get("task", {}).get("primary_language", "en")
        for path in os.listdir(os.path.join(task_path, "statement")):
            digest = self.file_cacher.put_file_from_path(
                os.path.join(task_path, "statement", path),
                "Statement for task %s (lang: %s)" % (name,
                                                      primary_language))
            break
        else:
            logger.critical("Couldn't find any task statement, aborting...")
            sys.exit(1)
        args["statements"] = [Statement(primary_language, digest)]
        args["primary_statements"] = '["%s"]' % (primary_language)
        args["submission_format"] = [
            SubmissionFormatElement("%s.%%l" % name)]
        args["token_mode"] = "disabled"
        
        args.update(self.token_mode)

        # Load attachments
        args["attachments"] = []
        if os.path.exists(os.path.join(task_path, "attachments")):
            for filename in os.listdir(os.path.join(task_path, "attachments")):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(task_path, "attachments", filename),
                    "Attachment %s for task %s" % (filename, name))
                args["attachments"] += [Attachment(filename, digest)]
        
        task = Task(**args)

        args = {}
        args["task"] = task
        args["description"] = "Default"
        args["autojudge"] = False
        args["time_limit"] = 2.0
        args["memory_limit"] = 256
        args["task_type"] = "Batch"
        args["score_type"] = "Sum"
        input_file = ""
        output_file = ""
        args["managers"] = []

        # Overwrite parameters
        for key, param in conf.iteritems():
            if key == "input":
                input_file = param
            elif key == "output":
                output_file = param
            elif key == "time_limit":
                args[key] = float(param)
            elif key in self.timedelta_params:
                args[key] = timedelta(seconds=param)
            elif key != "subtasks_parameters" and key != "subtasks":
                args[key] = param

        # Intelligent tests format detector
        # Load all tests recursively
        def load_tests(tests_path, name):
            if os.path.isfile(os.path.join(tests_path, name)):
                return [name]
            elif os.path.isdir(os.path.join(tests_path, name)):
                l = []
                for path in os.listdir(os.path.join(tests_path, name)):
                    l += load_tests(tests_path, os.path.join(name, path))
                return l
            else:
                return []
        full_names = load_tests(os.path.join(task_path, "tests"), "")
        tests_dict = dict((os.path.split(test)[-1], test)
                    for test in full_names)
        tests = []
        detected = False
        tests_format = 0
        if not detected:
            # * / *.a format
            detected = True
            for test in tests_dict.keys():
                if test.endswith(".a"):
                    if test[:-2] not in tests_dict.keys():
                        detected = False
                else:
                    if test + ".a" not in tests_dict.keys():
                        detected = False
            if detected:
                logger.info("Tests format * / *.a detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if not short_name.endswith(".a"):
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name + ".a"],
                                      "public": False })
                        idx += 1
            tests_format = 1
        if not detected:
            # *.in* / *.out* format
            detected = True
            for test in tests_dict.keys():
                if test.find(".in") != -1:
                    if test.replace(".in", ".out") not in tests_dict.keys():
                        detected = False
                elif test.find(".out"):
                    if test.replace(".out", ".in") not in tests_dict.keys():
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format *.in* / *.out* detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if short_name.find(".in") != -1:
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name.replace(".in", ".out")],
                                      "public": False })
                        idx += 1
            tests_format = 2
        if not detected:
            # *input* / *output* format
            detected = True
            for test in tests_dict.keys():
                if test.find("input") != -1:
                    if test.replace("input", "output") not in tests_dict.keys():
                        detected = False
                elif test.find("output"):
                    if test.replace("output", "input") not in tests_dict.keys():
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format *input* / *output* detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if short_name.find("input") != -1:
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name.replace("input", "output")],
                                      "public": False })
                        idx += 1
            tests_format = 3
        if not detected:
            # Need more intelligence
            logger.critical("Sorry, I can't recognize tests format")
            sys.exit(1)

        # Detect subtasks
        if "subtasks_parameters" in conf:
            logger.info("Detected simple subtask description")
            args["score_type"] = "NamedGroup"
            subtasks = conf["subtasks_parameters"]
            total_value = float(subtasks.get("total_value", "100.0"))
            is_public = subtasks.get("public_tests", False)
            if is_public:
                for test in tests:
                    test["public"] = True
            samples = list(int(test.strip()) - 1
                            for test in 
                            subtasks.get("sample_tests", "").strip().split(","))
            for i in samples:
                tests[i]["public"] = True
            samples_group = {
                "score": 0,
                "type": "sum",
                "public": rebuild_list(samples),
                "private": [],
                "hidden": [] }
            tests_group = {
                "score": total_value,
                "type": "sum",
                "public": [],
                "private": [],
                "hidden": [] }
            for i in xrange(len(tests)):
                if not i in samples:
                    if is_public:
                        tests_group["public"].append(i)
                    else:
                        tests_group["private"].append(i)
            tests_group["public"] = rebuild_list(tests_group["public"])
            tests_group["private"] = rebuild_list(tests_group["private"])
            args["score_type_parameters"] = json.dumps([samples_group, tests_group])
        elif "subtasks" in conf:
            logger.info("Detected full subtask description")
            args["score_type"] = "NamedGroup"
            subtasks = conf.get("subtasks")
            for subtask in subtasks:
                if subtask["score"] is None:
                    subtask["score"] = 0.0
                if subtask["type"] is None:
                    subtask["type"] = "sum"
                subtask["public"] = rebuild_list(subtask["public"])
                subtask["private"] = rebuild_list(subtask["private"])
                subtask["hidden"] = rebuild_list(subtask["hidden"])
                for i in subtask["public"]:
                    tests[int(i)]["public"] = True
            args["score_type_parameters"] = json.dumps(conf.get("subtasks"))
        else:
            args["score_type"] = "Sum"
            total_value = 100.0
            input_value = 0.0
            if len(tests) != 0:
                input_value = total_value / len(tests)
            args["score_type_parameters"] = str(input_value)

        # Load testcases
        args["testcases"] = []
        for test in tests:
            i = test["idx"]
            input_digest = self.file_cacher.put_file_from_path(
                os.path.join(task_path, "tests", test["input"]),
                "Input %d for task %s" % (i, name))
            output_digest = self.file_cacher.put_file_from_path(
                os.path.join(task_path, "tests", test["output"]),
                "Output %d for task %s" % (i, name))
            args["testcases"] += [
                Testcase("%03d" % i, test["public"], input_digest, output_digest)]

        # Load graders (and stubs if any)
        if os.path.isdir(os.path.join(task_path, "graders")):
            for filename in os.listdir(os.path.join(task_path, "graders")):
                digest = self.file_cacher.put_file_from_path(
                    os.path.join(task_path, "graders", filename),
                    "Grader %s for task %s" % (filename, name))
                args["managers"] += [
                    Manager(filename, digest)]
            compilation_param = "grader"
        else:
            compilation_param = "alone"

        # Load checker
        paths = [os.path.join(task_path, "checker"),
                 os.path.join(task_path, "check"),
                 os.path.join(task_path, "check.exe")]
        for path in paths:
            if os.path.isfile(path):
                digest = self.file_cacher.put_file_from_path(
                    path,
                    "Checker for task %s" % name)
                args["managers"] += [
                    Manager("checker", digest)]
                evaluation_param = "comparator"
                break
        else:
            evaluation_param = "diff"

        # If the task type is Communication, try to load manager
        path = os.path.join(task_path, "manager")
        if os.path.isfile(path):
            args["task_type"] = "Communication"
            args["task_type_parameters"] = '[]'
            digest = self.file_cacher.put_file_from_path(
                path,
                "Manager for task %s" % name)
            args["managers"] += [
                Manager("manager", digest)]

        # Set task type parameters
        if args["task_type"] == "OutputOnly":
            args["time_limit"] = None
            args["memory_limit"] = None
            args["task_type_parameters"] = '["%s"]' % evaluation_param
            task.submission_format = [
                SubmissionFormatElement("%03d.out" % i)
                for i in xrange(len(tests))]
        elif args["task_type"] == "Batch":
            args["task_type_parameters"] = \
                '["%s", ["%s", "%s"], "%s"]' % \
                (compilation_param, input_file, output_file,
                evaluation_param)

        logger.info("Task type is %s" % args["task_type"])
        dataset = Dataset(**args)
        task.active_dataset = dataset
        logger.info("Task parameters loaded.")
        return task
