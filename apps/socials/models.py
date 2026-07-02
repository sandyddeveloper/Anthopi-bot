from django.db import models


class SocialAccount(models.Model):
    platform = models.CharField(max_length=50)
    username = models.CharField(max_length=255)
    access_token = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform}:{self.username}"
