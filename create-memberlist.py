#!/usr/bin/env python3

# Copyright (c) 2022 Samuel Mehrbrodt
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import churchtoolsapi

from py3o.template import Template

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--filter-status", help="Filter by status")

parser.add_argument("--template", default="template_memberlist.odt", help="custom template file (odt)")
parser.add_argument("--output", default="memberlist.odt", help="output file (odt)")
parser.add_argument("--log", default=None, help="log file")
args = parser.parse_args()

# Create template
t = Template(args.template, args.output)

if(args.log != None):
    logging.basicConfig(filename=args.log, level=logging.INFO)


persons_sorted = churchtoolsapi.get_persons(args.filter_status.split(","), include_images=True)

# todo: filter by group and role

data = dict(persons=persons_sorted)
t.render(data)


