import logging
import urllib.error
import urllib.parse
import urllib.request

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from lti import ToolConfig

import slack_provisioning.util as util
from slack_provisioning.slack_api import (assign_user_to_workspace,
                                          create_slack_workspace,
                                          get_default_workspace_channels,
                                          get_or_create_user_id,
                                          get_scim_user_by_email,
                                          is_user_in_workspace,
                                          is_user_workspace_admin,
                                          set_workspace_admin,
                                          set_team_icon)
from .models import SlackWorkspace

logger = logging.getLogger(__name__)


@require_http_methods(['GET'])
def tool_config(request):
    url = "https://{}{}".format(request.get_host(), reverse('sp:lti_launch'))
    url = _url(url)

    title = 'Slack'
    lti_tool_config = ToolConfig(
        title=title,
        launch_url=url,
        secure_launch_url=url,
        description="This LTI tool provisions a Slack workspace for the course it is installed in."
    )

    # this is how to tell Canvas that this tool provides an account navigation link:
    nav_params = {
        'enabled': 'true',
        'text': title,
        'default': 'disabled',
        'visibility': 'members'
    }
    custom_fields = {
        'canvas_membership_roles': '$Canvas.membership.roles',
        'canvas_term_name': '$Canvas.term.name',
        'canvas_course_sectionsissourceids': '$Canvas.course.sectionSisSourceIds',
        'canvas_person_email_sis': '$vnd.Canvas.Person.email.sis',
    }

    lti_tool_config.set_ext_param('canvas.instructure.com', 'custom_fields', custom_fields)
    lti_tool_config.set_ext_param('canvas.instructure.com', 'course_navigation', nav_params)
    lti_tool_config.set_ext_param('canvas.instructure.com', 'privacy_level', 'public')

    return HttpResponse(lti_tool_config.to_xml(), content_type='text/xml')


def _url(url):
    """
    *** Taken from ATG's django-app-lti repo to fix the issue of resource_link_id being included in the launch url
    *** TLT-3591
    Returns the URL with the resource_link_id parameter removed from the URL, which
    may have been automatically added by the reverse() method. The reverse() method is
    patched by django-auth-lti in applications using the MultiLTI middleware. Since
    some applications may not be using the patched version of reverse(), we must parse the
    URL manually and remove the resource_link_id parameter if present. This will
    prevent any issues upon redirect from the launch.
    """

    parts = urllib.parse.urlparse(url)
    query_dict = urllib.parse.parse_qs(parts.query)
    if 'resource_link_id' in query_dict:
        query_dict.pop('resource_link_id', None)
    new_parts = list(parts)
    new_parts[4] = urllib.parse.urlencode(query_dict)
    return urllib.parse.urlunparse(new_parts)


@login_required
@require_http_methods(['POST'])
@csrf_exempt
def lti_launch(request):
    # Check if there is already a Slack workspace for the current course
    # If there is no workspace and the user is a course staff member, allow user to create space via button in template
    # If there is no workspace and the user is not staff, display message that states staff needs to provision
    # If there is a workspace and the current user is not a member, display message for user to join
    # If there is a workspace and the current user is a member, display workspace info

    course_sis_id = request.LTI.get('lis_course_offering_sourcedid')
    logger.info('inside lti_launch')

    user_roles = request.LTI.get('roles')

    # make sure this user has an appropriate role before going further
    if not util.is_user_in_class(user_roles=user_roles):
        logger.warning(f'Slack tool launched without an appropriate role: {user_roles}')
        context = {
            'message': "Sorry, you don't have permission to use this tool.",
        }
        return render(request, 'slack_provisioning/error.html', context)

    univ_id = request.LTI.get('lis_person_sourcedid')
    user_email = request.LTI.get('custom_canvas_person_email_sis')

    scim_user = get_scim_user_by_email(user_email)
    user_is_staff = util.is_user_staff(user_roles=user_roles)

    logger.debug(request.LTI)
    logger.debug(f'course_sis_id:{course_sis_id}  user_is_staff:{user_is_staff}')

    slack_workspace = None
    workspace_member = False

    try:
        slack_workspace = SlackWorkspace.objects.get(course_sis_id=course_sis_id)
        logger.debug(slack_workspace)
        if slack_workspace and slack_workspace.status == 'completed':
            # the workspace exists and is ready for use
            team_id = slack_workspace.team_id
            if scim_user:
                # the user already has a Grid user account
                slack_user_id = scim_user['id']
                workspace_member = is_user_in_workspace(user_id=slack_user_id, team_id=team_id)
                if workspace_member and user_is_staff:
                    workspace_admin = is_user_workspace_admin(user_id=slack_user_id, team_id=team_id)
                    if not workspace_admin:
                        # this user may have been invited directly in Slack, and didn't join via this tool initially
                        logger.info(f'user {slack_user_id} is staff but not an admin of {team_id} - setting admin role now')
                        set_workspace_admin(team_id=team_id, user_id=slack_user_id)
    except SlackWorkspace.DoesNotExist:
        logger.debug(f'Workspace does not currently exist for course instance {course_sis_id}')
    except Exception as e:
        logger.exception(f'Exception in the LTI launch process, {e}')

    context = {
        'slack_workspace': slack_workspace,
        'user_is_staff': user_is_staff,
        'workspace_member': workspace_member,
        'existing_slack_user': True if scim_user else False,
        'course_sis_id': course_sis_id,
        'univ_id': univ_id,
        'user_email': user_email,
    }
    logger.debug(f'about to render the launch template with this context: {context}')

    response = render(request, 'slack_provisioning/lti_launch.html', context)
    response['Access-Control-Allow-Origin'] = '*'
    return response

@require_http_methods(['POST'])
@login_required
def provision_slack_workspace(request):
    """
    Handles the process when a course staff member clicks the "Provision Slack Workspace" button when an space
    does not currently exist.
    Create a Django workspace obj
    """
    logger.debug(request.LTI)

    term_name = request.LTI.get('custom_canvas_term_name')
    course_code = request.LTI.get('context_label')
    course_title = request.LTI.get('context_title')
    course_sis_id = request.LTI.get('lis_course_offering_sourcedid')
    user_roles = request.LTI.get('roles')
    univ_id = request.LTI.get('lis_person_sourcedid')
    user_email = request.LTI.get('custom_canvas_person_email_sis')
    user_is_staff = util.is_user_staff(user_roles=user_roles)
    context = {}
    if user_is_staff:
        slack_user_id = get_or_create_user_id(user_email)

        logger.debug(f'LTI: {request.LTI}')

        errors = False

        team_domain = util.get_team_domain(course_code, term_name)
        team_name = util.get_team_name(course_code, term_name, course_sis_id)

        # Create workspace obj with default status of "pending" and add to SQS for processing
        slack_workspace = SlackWorkspace.objects.create(
            team_domain=team_domain,
            team_name=team_name,
            created_by=univ_id,
            course_sis_id=course_sis_id
        )

        api_call = create_slack_workspace(
            team_domain=team_domain,
            team_name=team_name,
            description=course_title,
        )

        if api_call['ok'] or api_call['ok'] == 'True':
            team_id = api_call['team']
            logger.info(f'Successful workspace creation for course {course_sis_id} - new team ID is {team_id}')
            slack_workspace.team_id = team_id
            slack_workspace.save()
            # Set the team icon
            set_team_icon(team_id, 'https://tlt-static-prod.s3.amazonaws.com/shields/fas.png')
            default_channels = get_default_workspace_channels(team_id=team_id)
            assign_user_to_workspace(user_id=slack_user_id, team_id=team_id, channel_ids=default_channels)
            set_workspace_admin(team_id=team_id, user_id=slack_user_id)
            slack_workspace.status = 'completed'
            slack_workspace.save()
            context['slack_workspace'] = slack_workspace
        else:
            logger.error(f'Error while trying to create a Slack workspace for course instance {course_sis_id}: {api_call}')
            errors = True

            slack_workspace.status = 'failed'
            slack_workspace.save()

    context['errors'] = errors

    return render(request, 'slack_provisioning/provision_slack_workspace.html', context)


@require_http_methods(['POST'])
@login_required
def join_slack_workspace(request):
    context = {}
    errors = False

    user_roles = request.LTI.get('roles')
    # Make sure this user has an appropriate role before going further
    if not util.is_user_in_class(user_roles=user_roles):
        logger.warning(f'Slack tool launched without an appropriate role: {user_roles}')
        context = {
            'message': "Sorry, you don't have permission to use this tool.",
        }
        return render(request, 'slack_provisioning/error.html', context)

    course_sis_id = request.LTI.get('lis_course_offering_sourcedid')
    univ_id = request.LTI.get('lis_person_sourcedid')
    user_email = request.LTI.get('custom_canvas_person_email_sis')
    slack_user_id = get_or_create_user_id(user_email)
    user_is_staff = util.is_user_staff(user_roles=user_roles)
    slack_workspace = SlackWorkspace.objects.get(course_sis_id=course_sis_id)

    context['slack_workspace'] = slack_workspace

    workspace_member = is_user_in_workspace(user_id=slack_user_id, team_id=slack_workspace.team_id)
    if not workspace_member:
        logger.info(f'Current user ({univ_id}) is not a member of the workspace ({slack_workspace.team_id}), '
                    f'Assigning user now.')
        default_channels = get_default_workspace_channels(team_id=slack_workspace.team_id)
        user_assigned = assign_user_to_workspace(user_id=slack_user_id, team_id=slack_workspace.team_id,
                                                 channel_ids=default_channels)
        if not user_assigned:
            errors = True
        else:
            if user_is_staff:
                logger.info(f'User is a staff member for course instance {course_sis_id}, '
                            f'making them a admin for workspace {slack_workspace.team_id} now.')
                set_workspace_admin(team_id=slack_workspace.team_id, user_id=slack_user_id)

    context['errors'] = errors

    return render(request, 'slack_provisioning/join_slack_workspace.html', context)


def lti_oauth_error(request):
    context = {
        'message': 'LTI authentication failed.'
    }
    return render(request, 'slack_provisioning/error.html', context)
