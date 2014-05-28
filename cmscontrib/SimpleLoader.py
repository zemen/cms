#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Konstantin Semenov <zemen17@gmail.com>
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
import re
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

def rebuild_list(old, test_list = [], delta = 0):
    l = []
    if old is None:
        return l
    if not isinstance(old, list):
        old = [old]
    for s in old:
        s = str(s).strip()
        if s.isdigit():
            l.append("%03d" % (int(numbers[0]) - delta))
        else:
            numbers = str(s).strip().split('-')
            if len(numbers) == 2 and numbers[0].isdigit() and numbers[1].isdigit():
                for i in xrange(int(numbers[0]) - delta, int(numbers[1]) - delta + 1):
                    l.append("%03d" % i)
            else:
                # Try matching tests with regex
                expr = re.compile(s)
                for t in test_list:
                    if re.match(expr, t["input"]):
                        l.append("%03d" % int(t["idx"]))
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
        logger.info("Load task %s" % name)

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
        
        args.update(conf.get("task", {}))
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
            elif key != "subtasks_parameters" and key != "subtasks" and key != "task":
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

        if not detected:
            # *.in* / *.out* format
            detected = True
            for test in tests_dict.keys():
                if test.find(".in") != -1:
                    if test.replace(".in", ".out") not in tests_dict.keys():
                        detected = False
                elif test.find(".out") != -1:
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

        if not detected:
            # *.in* / *.sol* format
            detected = True
            for test in tests_dict.keys():
                if test.find(".in") != -1:
                    if test.replace(".in", ".sol") not in tests_dict.keys():
                        detected = False
                elif test.find(".sol") != -1:
                    if test.replace(".sol", ".in") not in tests_dict.keys():
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format *.in* / *.sol* detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if short_name.find(".in") != -1:
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name.replace(".in", ".sol")],
                                      "public": False })
                        idx += 1

        if not detected:
            # *.in* / *.res* format
            detected = True
            for test in tests_dict.keys():
                if test.find(".in") != -1:
                    if test.replace(".in", ".res") not in tests_dict.keys():
                        detected = False
                elif test.find(".res") != -1:
                    if test.replace(".res", ".in") not in tests_dict.keys():
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format *.in* / *.res* detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if short_name.find(".in") != -1:
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name.replace(".in", ".res")],
                                      "public": False })
                        idx += 1

        if not detected:
            # *.in* / *.ans* format
            detected = True
            for test in tests_dict.keys():
                if test.find(".in") != -1:
                    if test.replace(".in", ".ans") not in tests_dict.keys():
                        detected = False
                elif test.find(".ans") != -1:
                    if test.replace(".ans", ".in") not in tests_dict.keys():
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format *.in* / *.ans* detected")
                idx = 0
                for (short_name, test) in sorted(tests_dict.items()):
                    if short_name.find(".in") != -1:
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": tests_dict[short_name.replace(".in", ".ans")],
                                      "public": False })
                        idx += 1

        if not detected:
            # *input* / *output* format
            detected = True
            for test in tests_dict.keys():
                if test.find("input") != -1:
                    if test.replace("input", "output") not in tests_dict.keys():
                        detected = False
                elif test.find("output") != -1:
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

        if not detected:
            # in* out* format using full paths
            detected = True
            for test in full_names:
                if test.startswith("in"):
                    if "out" + test[2:] not in full_names:
                        detected = False
                elif test.startswith("out"):
                    if "in" + test[3:] not in full_names:
                        detected = False
                else:
                    detected = False
            if detected:
                logger.info("Tests format in* / out* with full paths detected")
                idx = 0
                for test in sorted(full_names):
                    if test.startswith("in"):
                        tests.append({"idx": idx,
                                      "input": test,
                                      "output": "out" + test[2:],
                                      "public": False })
                        idx += 1

        if not detected:
            # Need more intelligence
            logger.critical("Sorry, I can't recognize tests format")
            sys.exit(1)

        # Detect subtasks
        if "subtasks_parameters" in conf:
            logger.info("Detected simple subtask description")
            args["score_type"] = "NamedGroup"
            subtasks = conf["subtasks_parameters"]
            total_value = float(subtasks.get("total_value", 100))
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
            if len(samples) == 0:
                args["score_type_parameters"] = json.dumps([tests_group])
            else:
                args["score_type_parameters"] = json.dumps([samples_group, tests_group])
        elif "subtasks" in conf:

            logger.info("Detected full subtask description")
            args["score_type"] = "NamedGroup"
            subtasks = conf.get("subtasks")
            for subtask in subtasks:
                if not "score" in subtask:
                    subtask["score"] = 0
                if not "type" in subtask:
                    subtask["type"] = "sum"
                if subtask["type"] != "sum" and subtask["type"] != "min":
                    # Custom evaluator parameter
                    with open(os.path.join(task_path, subtask["type"]), "r") as prog_file:
                        prog = prog_file.read()
                    subtask["type"] = prog
                subtask["public"] = rebuild_list(subtask.get("public", []), test_list = tests, delta = 1)
                subtask["private"] = rebuild_list(subtask.get("private", []), test_list = tests, delta = 1)
                subtask["hidden"] = rebuild_list(subtask.get("hidden", []), test_list = tests, delta = 1)
                for i in subtask["public"]:
                    tests[int(i)]["public"] = True
            args["score_type_parameters"] = json.dumps(conf.get("subtasks"))
        else:

            logger.info("Subtask description was not detected")
            args["score_type"] = "NamedGroup"
            # Autodetect samples
            samples = []
            for test in tests:
                if test["input"].find("dummy") != -1 or test["input"].find("sample") != -1:
                    samples.append(test["idx"])
            for i in samples:
                tests[i]["public"] = True
            samples_group = {
                "score": 0,
                "type": "sum",
                "public": rebuild_list(samples),
                "private": [],
                "hidden": [] }
            tests_group = {
                "score": 100,
                "type": "sum",
                "public": [],
                "private": [],
                "hidden": [] }
            for i in xrange(len(tests)):
                if not i in samples:
                    tests_group["private"].append(i)
            tests_group["public"] = rebuild_list(tests_group["public"])
            tests_group["private"] = rebuild_list(tests_group["private"])
            if len(samples) == 0:
                args["score_type_parameters"] = json.dumps([tests_group])
            else:
                args["score_type_parameters"] = json.dumps([samples_group, tests_group])

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
                SubmissionFormatElement("%03d.out" % (i + 1))
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
