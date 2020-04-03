import logging
import random

import requests
from django.conf import settings


logger = logging.getLogger(__name__)

SLACK_ENDPOINT = 'https://slack.com/api/'
SLACK_SCIM_ENDPOINT = 'https://api.slack.com/scim/v1/'
SLACK_TOKEN = settings.SLACK_PROVISIONING['slack_api_token']

# Visit https://api.slack.com/methods for additional information on the Slack API.


def create_slack_workspace(team_domain, team_name, team_discoverability='unlisted', description=None):
    """
    This Admin API creates a workspace for an enterprise organization with the given params.
    Tier 1 (1+ per minute)
    :param team_domain: Team domain that will be used in the Slack endpoint, eg: class-101 = class-101.slack.com
    :param team_name: Display name for the workspace, eg: Class 101 Summer
    :param team_discoverability: Default is unlisted to hide visibility from other users in the grid.
    :param description: Description of the workspace. eg: Class 101 is a summer class
    :return: Returns the status ("ok":True/False) and if success will return the team ID of the new workspace.
    """
    params = {
        'token': SLACK_TOKEN,
        'team_domain': team_domain,
        'team_name': team_name,
        'team_description': description,
        'team_discoverability': team_discoverability
    }

    req = requests.post(url=SLACK_ENDPOINT+'admin.teams.create',
                        data=params)

    logger.info(f'Response data from creating a workspace, '
                f'domain:{team_domain}, team_name:{team_name}, response data {req.json()}')

    return req.json()


def invite_user_to_workspace(channel_ids, email, team_id):
    """
    This Admin API invites a user to a workspace from the given params.
    Tier 2 (20+ per minute)
    :param channel_ids: The channel ID's of the workspace to grant the user access to.
    :param email: The email address of the user to be invited.
    :param team_id: The Slack workspace team ID to invite the user to.
    :return: Returns the status of the API call ("ok":True/False)
    """
    params = {
        'token': SLACK_TOKEN,
        'channel_ids': channel_ids,
        'email': email,
        'team_id': team_id
    }

    req = requests.post(url=SLACK_ENDPOINT+'admin.users.invite',
                        data=params)

    logger.info(f'Response data from inviting a user to workspace, '
                f'team id:{team_id}, email:{email}, response data {req.json()}')

    return req.json()


def set_workspace_admin(team_id, user_id):
    """
    Set an existing guest, regular user, or owner to be an admin user.
    Tier 2 (20+ per minute)
    :param team_id: The Slack workspace team ID that the given user_id will be set admin to.
    :param user_id: The Slack user_id that is to be promoted to admin.
    :return:
    """
    params = {
        'token': SLACK_TOKEN,
        'team_id': team_id,
        'user_id': user_id
    }

    req = requests.post(url=SLACK_ENDPOINT+'admin.users.setAdmin',
                        data=params)

    logger.info(f'Response data from setting workspace admin, '
                f'team id:{team_id}, user_id:{user_id}, response data {req.json()}')

    return req.json()


def list_workspace_users(team_id):
    """
    List all users of a given Slack workspace team id.
    Re pagination, the default limit is 100 per page
    Tier 3 (50+ per minute)
    :param team_id: The Slack workspace team ID to retrieve user data from.
    :return: A list of Slack workspace users from the given team_id.
    """
    params = {
        'token': SLACK_TOKEN,
        'team_id': team_id
    }
    # will need to deal with pagination
    req = requests.post(url=SLACK_ENDPOINT+'admin.users.list',
                        data=params)

    logger.info(f'Response data from listing workspace users, '
                f'team id:{team_id}, response data {req.json()}')

    return req.json()


def get_scim_user_by_email(email):
    """
    Retrieves a single user resource by email
    :param email: The email to use when retrieving a Slack user
    :return: Slack user information
    """
    params = {
        'filter': f'email eq {email}',
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    req = requests.get(url=SLACK_SCIM_ENDPOINT+'Users', headers=headers, params=params)
    if req.status_code == 200:
        response_data = req.json()
        try:
            if response_data['totalResults'] == 1:
                return response_data['Resources'][0]
            elif response_data['totalResults'] == 0:
                logger.warning(f'No Slack user found matching {email}')
                return None
            else:
                raise SlackApiError(f'Multiple Slack users found matching {email}')

        except KeyError:
            logger.error(f'Got unexpected data in SCIM response: {response_data}')
    else:
        logger.error(f'Slack SCIM API error {req.status_code}: {req.text}')

    return None


def is_user_in_workspace(user_id, team_id):
    """
    Determines if the given user is in the given team.
    :return: A boolean that indicates if the given user id is in the given team.
    """
    params = {
        'user': user_id
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    # get the user and check their teams array
    req = requests.get(url=SLACK_ENDPOINT+'users.info', headers=headers, params=params)
    if req.status_code == 200:
        response_data = req.json()
        try:
            if team_id in response_data['user'].get('teams', []):
                return True
            else:
                return False
        except KeyError:
            logger.error(f'Got unexpected data in API response: {response_data}')
    else:
        logger.error(f'Slack API error {req.status_code}: {req.text}')

    return False


def is_user_workspace_admin(user_id, team_id):
    """
    :return: Returns a boolean indicating if the given user is an admin member type in the given team.
    """

    params = {
        'team_id': team_id,
        'limit': 100,
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    req = requests.get(url=SLACK_ENDPOINT+'admin.teams.admins.list', headers=headers, params=params)
    if req.status_code == 200:
        response_data = req.json()
        try:
            if user_id in response_data['admin_ids']:
                return True
            else:
                return False

        except KeyError:
            logger.error(f'Got unexpected data in API response: {response_data}')
    else:
        logger.error(f'Slack API error {req.status_code}: {req.text}')

    return False


def get_team_info(team_id):
    """
    This Admin API method fetches information about settings in a workspace.
    Tier 3 (50+ per minute).
    :param team_id: The Slack workspace team_id to get information for.
    :return: Returns team information from the given team_id if it exists.
    """
    params = {
        'team_id': team_id,
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    req = requests.get(url=SLACK_ENDPOINT+'admin.teams.settings.info', headers=headers, params=params)
    if req.status_code == 200:
        response_data = req.json()
        try:
            team = response_data['team']
            return team

        except KeyError:
            logger.error(f'Got unexpected data in API response: {response_data}')
    else:
        logger.error(f'Slack API error {req.status_code}: {req.text}')

    return None


def get_default_workspace_channels(team_id):
    """
    :return: Returns a comma separated list of channel ID's of the given team ID. eg: 'C0105PLQG9G’, ‘C010H7XGDCD'
    """
    return ','.join(get_team_info(team_id=team_id).get('default_channels'))


def set_team_icon(team_id, image_url):
    """
    Sets the given workspace's icon to be the image from the given image URL.
    """
    params = {
        'team_id': team_id,
        'image_url': image_url,
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    req = requests.get(url=SLACK_ENDPOINT+'admin.teams.settings.setIcon', headers=headers, params=params)
    response_data = req.json()
    return response_data


def get_or_create_user_id(email):
    """
    Returns a Slack user account if it exists or will create one using the SCIM API.
    """
    scim_user = get_scim_user_by_email(email)
    if scim_user:
        return scim_user['id']
    else:
        user_name = email.split('@')[0].lower()[:21]
        try:
            scim_user = create_scim_user(user_name, email)
        except SlackUsernameTakenError:
            logger.warning(f'Slack username {user_name} already exists; trying again with a random suffix')
            # add a random 3-digit number suffix to the username
            suffix = str(random.randint(100, 999))
            user_name = user_name[:18]+suffix
            scim_user = create_scim_user(user_name, email)

    return scim_user['id']


def create_scim_user(user_name, email):
    """
    Creates a Slack user account with the given user_name and given email.
    """
    params = {
        'schemas': [
            'urn:scim:schemas:core:1.0'
        ],
        'userName': user_name,
        'emails': [
            {
                'value': email,
                'primary': True,
            },
        ],
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }

    req = requests.post(url=SLACK_SCIM_ENDPOINT+'Users', headers=headers, json=params)
    response_data = req.json()
    logger.debug(req.text)
    if req.status_code in [200, 201]:
        scim_user = response_data
        return scim_user
    elif req.status_code == 409:
        if 'username_taken' in response_data['Errors']['description']:
            raise SlackUsernameTakenError(response_data['Errors']['description'])
        elif 'email_taken' in response_data['Errors']['description']:
            raise SlackEmailTakenError(response_data['Errors']['description'])

    else:
        logger.error(f'unexpected status code: {req.status_code}')
        raise SlackApiError(response_data)


def assign_user_to_workspace(team_id, user_id, channel_ids):
    """
    Assigns an existing Slack user account to the given team with the given channels.
    Tier 2 (20+ per minute)
    """
    params = {
        'team_id': team_id,
        'user_id': user_id,
        'channel_ids': channel_ids
    }
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
    }
    req = requests.get(url=SLACK_ENDPOINT+'admin.users.assign', headers=headers, params=params)
    if req.status_code == 200:
        return req.json()
    else:
        logger.error(f'Slack API error {req.status_code}: {req.text}')

    return None


class SlackApiError(Exception):
    pass


class SlackUsernameTakenError(SlackApiError):
    pass


class SlackEmailTakenError(SlackApiError):
    pass


class SlackUserCreationError(SlackApiError):
    pass


class SlackTooManyRequests(SlackApiError):
    pass
