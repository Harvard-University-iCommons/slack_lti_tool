from django.db import models


class SlackWorkspace(models.Model):
    STATUS_CHOICES = [
        ('pending', 'pending'),
        ('completed', 'completed'),
        ('failed', 'failed')
    ]
    team_domain = models.CharField(max_length=21)
    team_name = models.CharField(max_length=100)
    team_description = models.CharField(max_length=100, null=True)
    team_discoverability = models.CharField(max_length=30, null=True)
    team_id = models.CharField(max_length=30, null=True)
    course_sis_id = models.CharField(max_length=30, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=30)
    last_modified = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'slack_workspace'


class SlackWorkspaceMember(models.Model):
    MEMBERSHIP_CHOICES = [
        ('regular', 'regular'),
        ('owner', 'owner'),
        ('admin', 'admin')
    ]
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES, default='regular')
    slack_workspace = models.ForeignKey('SlackWorkspace', on_delete=models.CASCADE, related_name='members')
    univ_id = models.CharField(max_length=10)
    slack_user_id = models.CharField(max_length=20, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'slack_workspace_member'
