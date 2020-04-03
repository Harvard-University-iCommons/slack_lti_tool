from django.urls import path, re_path, include
from django.conf import settings

import slack_provisioning.views as views

urlpatterns = [
    path('lti_launch/', views.lti_launch, name='lti_launch'),
    path('lti_auth_error/', views.lti_oauth_error, name='lti_auth_error'),
    path('tool_config/', views.tool_config, name='tool_config'),
    path('provision_slack_workspace/', views.provision_slack_workspace, name='provision_slack_workspace'),
    path('join_slack_workspace/', views.join_slack_workspace, name='join_slack_workspace')
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns += [
            re_path(r'^__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass  # This is OK for a deployed instance running in DEBUG mode
