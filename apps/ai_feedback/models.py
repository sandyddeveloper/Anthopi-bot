from django.db import models
from apps.common.models import BaseModel
from apps.users.models import User
from apps.ai_chat.models import Conversation, Message

class Feedback(BaseModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='feedbacks')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='feedbacks')
    score = models.IntegerField(default=1)  # e.g., 1 for Helpful, -1 for Incorrect
    comment = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')

    def __str__(self):
        type_str = "Positive" if self.score > 0 else "Negative"
        return f"{type_str} Feedback on Message {self.message.id} by {self.user.email}"
