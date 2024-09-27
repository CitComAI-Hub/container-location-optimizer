```bash
docker run --name ocl-redis -d -p 6379:6379 redis
```

```bash
docker run --name ocl-rabbitmq -d -p 5672:5672 rabbitmq
```

```bash
celery -A tasks worker --loglevel=info
```

```bash
flask --app server run
```