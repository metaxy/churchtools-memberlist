#!/usr/bin/env python3

# Copyright (c) 2022 Samuel Mehrbrodt
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import json
import churchtoolsapi

from py3o.template import Template
import copy

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--filter-status", help="Filter by status")

parser.add_argument("--template", default="template_shepardlist.odt", help="custom template file (odt)")
parser.add_argument("--output", default="shepardlist.odt", help="output file (odt)")
parser.add_argument("--log", default=None, help="log file")
parser.add_argument("--cache", default=None, help="cache the response")
args = parser.parse_args()

# Create template
t = Template(args.template, args.output)

if(args.log != None):
    logging.basicConfig(filename=args.log, level=logging.INFO)

persons_sorted = churchtoolsapi.get_persons(args.filter_status.split(","), include_images=True, cache_response=args.cache)
# Calculate age for each person
for person in persons_sorted:
    try:
        person['AFS'] = next(group for group in person['groups'] if group.startswith('A-FS')).lstrip('A-FS').strip()
    except StopIteration:
        person['AFS'] = ''  # Set default value if 'A-FS' group is not found

    try:
        person['LFS'] = next(group for group in person['groups'] if group.startswith('L-FS')).lstrip('L-FS').strip()
    except StopIteration:
        person['LFS'] = ''  # Set default value if 'L-FS' group is not found

    try:
        person['JugendFS'] = next(group for group in person['groups'] if group.startswith('Jugend-FS')).lstrip('Jugend-FS').strip()
    except StopIteration:
        person['JugendFS'] = ''  # Set default value if 'L-FS' group is not found

    color = '#616161'
    if person['AFS'] == 'Paul Walger':
        color = '#FBC02D'
    elif person['AFS'] == 'Alexander Arzer':
        color = '#1565C0'
    elif person['AFS'] == 'Johann Friesen':
        color = '#D32F2F'
    
    person['image'] = churchtoolsapi.make_img_round(person['image_source'], color)

    person['AFS'] = ''.join(word[0].upper() for word in person['AFS'].split()) 
    if person['LFS'] != '':
        person['LFS'] = ' | ' + ''.join(word[0].upper() for word in person['LFS'].split())
    if person['JugendFS'] != '':
        person['JugendFS'] = ' | ' + ''.join(word[0].upper() for word in person['JugendFS'].split())



# todo: filter by group and role

persons_simple = copy.deepcopy(persons_sorted)
# Remove 'image' keys from persons
for person in persons_simple:
    person.pop('image', None)
    person.pop('image_source', None)

    person.pop('birthday_date', None)
    person.pop('children', None)
# pretty print persons as json

print(persons_simple)
print(json.dumps(persons_simple, indent=4))
data = dict(persons=persons_sorted)
t.render(data)


