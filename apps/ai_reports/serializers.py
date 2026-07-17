from rest_framework import serializers
from apps.ai_reports.models import AIReport

class AIReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIReport
        fields = ['id', 'organization', 'report_type', 'start_date', 'end_date', 'data', 'generated_by', 'created_at']
        read_only_fields = ['id', 'organization', 'data', 'generated_by', 'created_at']
