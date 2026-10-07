from celery import Celery

from app.database import settings

# The broker is the Redis the API already uses: the API pushes a task onto a
# list there and a worker process pops it off.
celery_app = Celery("aerofare", broker=settings.redis_url, include=["app.notifications.tasks"])

# Nothing reads a task's return value, so skip storing it (no result backend).
celery_app.conf.task_ignore_result = True
