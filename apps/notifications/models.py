from django.db import models
from apps.common.models import BaseModel
from apps.users.models import User

class Notification(BaseModel):
    TYPE_CHOICES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    event_type = models.CharField(max_length=100) # e.g. user_invited, user_joined, project_assigned, file_uploaded, password_changed
    action_url = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Notification for {self.recipient.email} - {self.title}"

class NotificationPreference(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_preferences')
    event_type = models.CharField(max_length=100)
    is_enabled_in_app = models.BooleanField(default=True)
    is_enabled_email = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'event_type')

    def __str__(self):
        return f"{self.user.email} preference for {self.event_type}"

def send_notification(recipient, sender, title, message, notification_type='info', event_type='general', action_url=''):
    # Check preferences
    pref = NotificationPreference.objects.filter(user=recipient, event_type=event_type).first()
    if pref and not pref.is_enabled_in_app:
        return None
        
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        title=title,
        message=message,
        notification_type=notification_type,
        event_type=event_type,
        action_url=action_url
    )

