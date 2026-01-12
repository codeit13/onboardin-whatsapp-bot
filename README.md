# Onboarding API

A production-ready FastAPI application with Celery task processing and webhook support.

## Features

- 🚀 FastAPI with multi-worker support
- 🔄 Celery for asynchronous task processing
- 🪝 Webhook handling with signature verification
- 📝 Structured logging
- 🛡️ Security middleware and error handling
- 📦 Modular, production-ready code structure
- ⚙️ Environment-based configuration

## Project Structure

```
Onboarding/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── celery_app.py           # Celery configuration
│   ├── dependencies.py         # FastAPI dependencies
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # API v1 router
│   │       └── endpoints/      # API endpoints
│   ├── core/
│   │   ├── config.py           # Application configuration
│   │   ├── logging_config.py   # Logging setup
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── exception_handlers.py # Exception handlers
│   │   └── middleware.py        # Custom middleware
│   ├── webhooks/
│   │   ├── router.py           # Webhook routes
│   │   └── handlers.py         # Webhook processing logic
│   ├── tasks/
│   │   ├── webhook_tasks.py    # Webhook Celery tasks
│   │   └── onboarding_tasks.py # Onboarding Celery tasks
│   ├── services/               # Business logic services
│   ├── models/                 # Data models and schemas
│   └── utils/                  # Utility functions
├── data/                       # Data files
├── logs/                       # Application logs
├── run.py                      # Server runner script
├── requirements.txt            # Python dependencies
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start Redis (Required for Celery)

```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt-get install redis-server && sudo systemctl start redis
```

### 5. Run the Application

```bash
# Development mode (single worker, auto-reload)
python run.py

# Production mode (multiple workers)
WORKERS=4 python run.py

# Without Celery
START_CELERY=false python run.py
```

### 6. Run Celery Worker (Separate Terminal)

```bash
celery -A app.celery_app worker --loglevel=info
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation (development only)
- `GET /redoc` - ReDoc documentation (development only)
- `POST /webhooks/` - Generic webhook endpoint
- `POST /webhooks/{provider}` - Provider-specific webhook endpoint
- `GET /api/v1/` - API v1 root

## Webhooks

### Generic Webhook

```bash
curl -X POST http://localhost:8001/webhooks/ \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-webhook-secret" \
  -d '{
    "event": "user.created",
    "data": {
      "user_id": "123",
      "email": "user@example.com"
    }
  }'
```

### Provider-Specific Webhook

```bash
curl -X POST http://localhost:8001/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-webhook-secret" \
  -d '{
    "type": "payment_intent.succeeded",
    "data": {...}
  }'
```

## Configuration

Key environment variables (see `.env.example` for full list):

- `DEBUG` - Enable debug mode
- `ENVIRONMENT` - Environment (development/staging/production)
- `WORKERS` - Number of uvicorn workers (auto-detected if not set)
- `CELERY_BROKER_URL` - Redis URL for Celery broker
- `WEBHOOK_SECRET` - Secret for webhook verification
- `SECRET_KEY` - Application secret key

## Development

### Code Structure

- **Core**: Configuration, logging, exceptions, middleware
- **API**: REST API endpoints organized by version
- **Webhooks**: Webhook handling and processing
- **Tasks**: Celery async tasks
- **Services**: Business logic layer
- **Models**: Pydantic schemas and data models
- **Utils**: Helper functions

### Adding New Endpoints

1. Create endpoint file in `app/api/v1/endpoints/`
2. Create router with FastAPI `APIRouter`
3. Include router in `app/api/v1/router.py`

### Adding New Webhooks

1. Add handler in `app/webhooks/handlers.py`
2. Add task in `app/tasks/webhook_tasks.py`
3. Update `_process_webhook_by_event` with new event type

### Adding New Celery Tasks

1. Create task in `app/tasks/`
2. Decorate with `@celery_app.task`
3. Import in `app/celery_app.py` if needed

## Production Deployment

1. Set `ENVIRONMENT=production` and `DEBUG=false`
2. Configure proper `SECRET_KEY` and `WEBHOOK_SECRET`
3. Use process manager (systemd, supervisor, etc.)
4. Set up reverse proxy (nginx, traefik, etc.)
5. Configure monitoring and logging
6. Use multiple workers: `WORKERS=4 python run.py`

## License

MIT

