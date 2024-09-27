```bash
docker run -d -p 5672:5672 rabbitmq
```

```bash
celery -A tasks worker --loglevel=info
```

```bash
flask --app server run
```