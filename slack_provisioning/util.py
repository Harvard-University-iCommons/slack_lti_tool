import json
import logging
import random
import re
import string

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

# from icommons_common.models import (CourseEnrollee, CourseGuest,
#                                     CourseInstance, CourseStaff)

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_ADMIN_ROLES = [
    'Instructor',
    'TA',
    'Designer',
    'urn:lti:instrole:ims/lis/Administrator'
]

DEFAULT_ALLOWED_MEMBER_ROLES = [
    'Learner',
]

ALLOWED_ADMIN_ROLES = settings.SLACK_PROVISIONING.get('allowed_admin_roles', DEFAULT_ALLOWED_ADMIN_ROLES)
ALLOWED_MEMBER_ROLES = settings.SLACK_PROVISIONING.get('allowed_member_roles', DEFAULT_ALLOWED_MEMBER_ROLES)

TERM_ABBRS = {
    'Fall': ('f', 'Fa'),
    'Spring': ('s', 'Sp'),
    'Winter': ('w', 'Wi'),
    'Summer': ('su', 'Sum'),
    'June': ('jun', 'Jun'),
    'July': ('jul', 'Jul'),
    'August': ('aug', 'Aug'),
    ' and ': ('', ''),
    'Full Year': ('fy', 'FY'),
    'Saturday': ('sat', 'Sat'),
    r'\s+': ('', ''),
    r'[^\w-]': ('', ''),
}


def is_user_staff(user_roles):

    matching = set(user_roles) & set(ALLOWED_ADMIN_ROLES)

    if len(matching) > 0:
        return True

    return False


def is_user_in_class(user_roles):

    matching = set(user_roles) & set(ALLOWED_ADMIN_ROLES + ALLOWED_MEMBER_ROLES)

    if len(matching) > 0:
        return True

    return False


def get_team_domain(course_code, term_name=''):
    random_string = _random_string(3)
    term_abbr = _abbreviate_term(term_name, 'domain')

    team_domain = re.sub(r'[^a-z0-9\-]', '-', course_code.lower())
    # add the term
    team_domain = team_domain + '-' + term_abbr
    # collapse consecutive '-' into one
    team_domain = re.sub('-+', '-', team_domain)
    # total length must be max 21 chars, minus 4 chars for separator + 3-char random_string
    team_domain = team_domain[:17]
    if team_domain[-1:] != '-':
        team_domain = team_domain + '-' + random_string
    else:
        team_domain = team_domain + random_string

    return team_domain


def get_team_name(course_code, term_name, course_sis_id=None):

    term_abbr = _abbreviate_term(term_name, 'name')

    # you may want to change the way this name is constructed; note that it needs to be unique within a Grid
    team_name = f'{course_code} ({term_abbr}) {course_sis_id}'

    # don't return more than 100 chars
    return team_name[:100]


def _abbreviate_term(term_name, type='domain'):
    """
    Our terms are named like "2019-2020 Fall", "2019-2020 Spring 1", etc.
    This function abbreviates these names for inclusion in a Slack team name or domain.
    For team name we abbreviate the term name to be like "Fa 19" or "Sp 20".
    For domain name we abbreviate the term name to be like "f-19" or "s-20".
    :param term_name: Term name from Canvas
    :param type: Either "name" or "domain" to indicate the type of abbreviation to return
    :return: Returns the abbreviated name in either name or domain format.
    """
    pat = r'(\d+)-?(\d*?)\s(.*)'
    m = re.match(pat, term_name)
    y1 = y2 = n = dname = label = None
    if m:
        y1 = m.group(1)
        y2 = m.group(2)
        n = m.group(3)
        dname = n
        label = n
        for (k, v) in TERM_ABBRS.items():
            dname = re.sub(k, v[0], dname)
            label = re.sub(k, v[1], label)
        if 'Spring' in n:
            y = y2
        else:
            y = y1
        dname = dname + y[-2:]
        label = label + y[-2:]
    else:
        # for the domain name just remove spaces and punctuation
        dname = re.sub(r'[^\w-]', '', term_name.lower())
        # for the name just use the term name as-is
        label = term_name

    if type == 'name':
        return label
    else:
        return dname


def _random_string(string_length=8):
    """Generate a random string of letters and digits """
    letters_and_digits = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters_and_digits) for i in range(string_length))
