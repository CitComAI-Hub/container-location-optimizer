# celeryconfig.py
from celery.schedules import crontab

# Define the beat schedule to run `update_data` every 10 minutes
beat_schedule = {
    'update-data-every-10-minutes': {
        'task': 'tasks.update_data',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}

broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
