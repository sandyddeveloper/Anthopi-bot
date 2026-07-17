from django.db import models
from apps.common.models import BaseModel
from apps.knowledge.models import File

class DocumentChunk(BaseModel):
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = models.JSONField(default=list)  # Storing floating point vector

    def __str__(self):
        return f"Chunk {self.chunk_index} for {self.file.name}"
