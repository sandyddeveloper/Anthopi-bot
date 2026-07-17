from celery import shared_task
from apps.ai_jobs.models import AIJob
import time

@shared_task
def run_ai_job_task(job_id):
    try:
        job = AIJob.objects.get(id=job_id)
        job.status = 'processing'
        job.save()
        
        # Fast processing simulation
        for i in range(1, job.total_items + 1):
            time.sleep(0.01)
            job.processed_items = i
            job.save()
            
        job.status = 'completed'
        job.result = {
            "summary": f"Completed background execution task '{job.task_name}' successfully.",
            "items_processed": job.total_items,
            "runtime_seconds": round(job.total_items * 0.01, 3)
        }
        job.save()
    except Exception as e:
        try:
            job = AIJob.objects.get(id=job_id)
            job.status = 'failed'
            job.result = {"error": str(e)}
            job.save()
        except Exception:
            pass
