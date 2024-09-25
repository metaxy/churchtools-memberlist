#!/usr/bin/env python3

# Copyright (c) 2022 Samuel Mehrbrodt
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import io
import pickle
import os
import requests
import json

from dotenv import load_dotenv
from os.path import exists
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from pyactiveresource.activeresource import ActiveResource

# DEBUG MODE (cache REST API result)
CACHE_RESPONSE = False
CACHED_FILENAME = "persons_{status_id}.dump"

# Random limits from Churchtools API
MAX_PERSONS_LIMIT = 500
MAX_GROUP_MEMBERS_LIMIT = 100



load_dotenv()

# REST API definitions
class ApiBase(ActiveResource):
    _site = 'https://' + os.getenv('CHURCHTOOLS_DOMAIN') + '/api/'
    _headers = { 'Authorization': 'Login ' + os.getenv('CHURCHTOOLS_LOGIN_TOKEN') }

class Group(ApiBase):
    pass

class Person(ApiBase):
    pass

class Child:
    def __lt__(self, other):
        return self.birthdate > other.birthdate

    def __str__(self):
        return self.name + self.age

def str_to_date(birthdate_str):
    if not birthdate_str:
        return datetime.date(1900, 1, 1)
    return datetime.datetime.strptime(birthdate_str, "%Y-%m-%d").date()

def __age(birthdate_str):
    if not birthdate_str:
        return 0
    birthdate = str_to_date(birthdate_str)
    today = datetime.date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
    return age

def format_date(birthdate_str):
    if not birthdate_str:
        return ""
    birthdate = str_to_date(birthdate_str)
    return birthdate.strftime("%d.%m.%Y")

# From https://note.nkmk.me/en/python-pillow-square-circle-thumbnail/
def __mask_circle_transparent(pil_img, blur_radius, offset=0):
    offset = blur_radius * 2 + offset
    mask = Image.new("L", pil_img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((offset, offset, pil_img.size[0] - offset, pil_img.size[1] - offset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur_radius))

    result = pil_img.copy()
    result.putalpha(mask)

    return result

def make_img_round(img_bytes, border_color=None):
    im = Image.open(io.BytesIO(img_bytes))
    im_round = __mask_circle_transparent(im, 0, 2)
    if(border_color != None):
        im_round = ImageOps.expand(im_round,border=8,fill=border_color)
    img_byte_arr = io.BytesIO()
    im_round.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def get_persons_by_status(filter_status=None, cache_response=False):
    cache_filename = "get_persons.dump"
    if cache_response and exists(cache_filename):
        with open(cache_filename, 'rb') as f:
            return pickle.load(f)

    if(filter_status != None):
        persons_result = Person.find(from_=ApiBase._site + 'persons', status_ids=filter_status, page=1, limit=MAX_PERSONS_LIMIT)
    else:
        persons_result = Person.find(from_=ApiBase._site + 'persons', page=1, limit=MAX_PERSONS_LIMIT)
    persons = persons_result[0]['data']

    persons_sorted = process_persons

    if cache_response:
        with open(cache_filename, 'wb') as f:
            pickle.dump(persons_sorted, f)

    return persons_sorted


def process_persons(persons, include_images=False):

    # Postprocessing
    for person in persons:
            # Get groups the person is enrolled in
        person_groups_url = ApiBase._site + 'persons/{id}/groups'.format(id=person['id'])
        person_groups_result = Group.find(from_=person_groups_url, limit=MAX_PERSONS_LIMIT)
        person_groups = person_groups_result[0]['data']

        group_names = [group['group']['title'] for group in person_groups]
        person['groups'] = group_names

        # Profile pic
        if include_images:
            if person['imageUrl']:
                person['image_source'] = requests.get(person['imageUrl']).content
            else:
                default_img_path = os.path.realpath(os.path.dirname(__file__)) + '/images/placeholder.png'
                img = open(default_img_path,'rb')
                person['image_source'] = bytes(img.read())

            # Make image round
            person['image'] = make_img_round(person['image_source'], 'red')

        # Format birthdate
        if person['birthday']:
            person['birthday_date'] = str_to_date(person['birthday'])
            person['age'] = __age(person['birthday'])
            person['birthday'] = format_date(person['birthday'])
        else:
            person['birthday_date'] = None
            person['age'] = 0

        # Relationships (Spouse, children)
        relationships_url = ApiBase._site + 'persons/{id}/relationships'.format(id=person['id'])
        relationships_result = Person.find(from_=relationships_url, limit=MAX_PERSONS_LIMIT)
        relationships = relationships_result[0]['data']
        person['children'] = []
        person['family_id'] = "{}-{}".format(person['lastName'], person['firstName'])
        person['familyEnd'] = False
        personHasSpouse = False
        if not relationships:
            person['familyEnd'] = True
        for relationship in relationships:
            if relationship['relationshipTypeId'] == 1 and relationship['degreeOfRelationship'] == 'relationship.part.child': # Kind
                child = Child()
                child.name = relationship['relative']['domainAttributes']['firstName']
                child_result = Person.find(from_=relationship['relative']['apiUrl'], limit=MAX_PERSONS_LIMIT)
                if len(child_result) > 0:
                    child.birthdate = str_to_date(child_result[0]['birthday'])
                    child.age = ' (' + str(__age(child_result[0]['birthday'])) + ')'
                    if(__age(child_result[0]['birthday']) < 18): #show children only if they are underage
                        person['children'].append(child)

            elif relationship['relationshipTypeId'] == 2: # Ehepartner
                personHasSpouse = True
                # Create family_id for sorting (last name, ID of husband & wife)
                if person['sexId'] == 1: # Male
                    person['family_id'] = '{lastname}-{husband_name}-{wife_name}-{husband_id}'.format(
                                            lastname=person['lastName'],
                                            husband_id=str(person['id']),
                                            husband_name=person['firstName'],
                                            wife_name=str(relationship['relative']['domainAttributes']['firstName']))
                else: # Female
                    person['family_id'] = '{lastname}-{husband_name}-{wife_name}-{husband_id}'.format(
                                            lastname=str(relationship['relative']['domainAttributes']['lastName']),
                                            husband_id=str(relationship['relative']['domainIdentifier']),
                                            husband_name=str(relationship['relative']['domainAttributes']['firstName']),
                                            wife_name=person['firstName'])
                    person['familyEnd'] = True

        if not personHasSpouse:
            person['familyEnd'] = True

        # Sort children by age
        person['children'].sort(reverse=True)

        # All children in one line
        person['allChildren'] = ', '.join(str(child) for child in person['children'])

        #Show children only once
        if (not personHasSpouse or person['sexId'] == 1):
            person['allChildrenOnce'] = ', '.join(str(child) for child in person['children'])
        else:
            person['allChildrenOnce'] = ''

    # Sort persons by their family
    persons_sorted = sorted(persons, key = lambda p: (p['family_id'], p['sexId']))

    # Cache result if in debug mode
    if cache_response:
        with open(cache_filename, 'wb') as f:
            pickle.dump(persons_sorted, f)

    return persons_sorted

class Member:
    personId = None
    firstName = ''
    lastName = ''
    present = False # Whether the person was present in the meeting

    def __hash__(self):
        return hash(self.personId)

    def __eq__(self, other):
        return self.personId == other.personId

    def __lt__(self, other):
        return self.lastName + self.firstName < other.lastName + other.firstName

    def __str__(self):
        return "{lastName} {firstName}".format(firstName = self.firstName, lastName = self.lastName)

def get_group_meeting(group_id, meeting_date):
    start_date_str = meeting_date.strftime("%Y-%m-%d")
    # End date must be one day more than start date
    end_date = meeting_date + datetime.timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")
    group_url = ApiBase._site + 'groups/{id}/meetings'.format(id=group_id)
    meetings_in_group_result = Group.find(from_=group_url,
        limit=1,
        start_date=start_date_str, end_date=end_date_str)
    meetings_in_group = meetings_in_group_result[0]['data']
    return meetings_in_group[0] if meetings_in_group else None

def get_meeting_members(group_id, meeting_id, filter_role_id=None):
    url = ApiBase._site + 'groups/{groupId}/meetings/{meetingId}/members'.format(groupId=group_id, meetingId=meeting_id)
    members_result = Group.find(from_=url)
    members = members_result[0]['data']
    new_members = []
    for member in members:
        if filter_role_id and int(member['member']['groupTypeRoleId']) != int(filter_role_id):
            continue
        new_member = Member()
        new_member.personId = member['member']['personId']
        new_member.firstName = member['member']['person']['domainAttributes']['firstName']
        new_member.lastName = member['member']['person']['domainAttributes']['lastName']
        new_member.present = member['status'] == 'present'
        new_members.append(new_member)
    return new_members
