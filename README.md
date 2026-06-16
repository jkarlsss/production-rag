# Production RAG API

A production-ready Retrieval-Augmented Generation (RAG) API built with FastAPI, LangGraph, LangSmith, and Google Gemini. This service provides secure, cached, and monitored endpoints for generating AI responses with built-in security checks, rate limiting, and observability.

## Features

- **Secure Input/Output Processing**: Injection detection and PII masking via a security pipeline
- **Response Caching**: Redis-style in-memory caching with TTL configuration
- **Rate Limiting**: Configurable requests per minute to prevent abuse
- **Observability**: 
  - LangSmith tracing for LLM calls
  - Prometheus-style metrics endpoint (`/metrics`)
  - Health check endpoint (`/health`)
  - Structured logging
- **Production Hardening**:
  - Dockerized with non-root user
  - Health checks
  - Graceful startup/shutdown
  - Error handling and validation
- **LangGraph Agent**: Extensible agent architecture for complex reasoning flows
- **Environment Configuration**: Easy configuration via `.env` file

## Architecture

```
┌─────────────────┐
│   HTTP Request  │
└─────────────────┘
          │
┌─────────────────┐
│ Security Check  │◄──┐
└─────────────────┘   │
          │           │
┌─────────────────┐   │
│   Cache Lookup  │   │
└─────────────────┐   │
          │           │
┌─────────────────┐   │
│ LangGraph Agent │   │
│   (Processing)  │   │
└─────────────────┘   │
          │           │
┌─────────────────┐   │
│ Security Check  │   │
│   (Output)      │   │
└─────────────────┘   │
          │           │
┌─────────────────┐   │
│   Cache Store   │   │
└─────────────────┘   │
          │           │
┌─────────────────┐   │
│ Metrics & Logs  │   │
└─────────────────┘   │
          │           │
┌─────────────────┐   │
│ HTTP Response   │◄──┘
└─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (optional, for containerized deployment)
- Google Gemini API key
- LangSmith API key (for tracing)

### Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```
5. Edit `.env` with your actual keys:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   LANGCHAIN_API_KEY=your_langsmith_api_key_here
   LANGCHAIN_PROJECT=your-project-name
   ```
6. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```
7. The API will be available at `http://localhost:8000`

### Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```
2. The API will be available at `http://localhost:8080` (mapped from container port 8000)
3. To run in detached mode:
   ```bash
   docker-compose up -d
   ```
4. To stop and remove containers:
   ```bash
   docker-compose down
   ```

## API Endpoints

### Chat Endpoint

```
POST /chat
```

Send a message to receive an AI-generated response.

**Request Body:**
```json
{
  "message": "Your question or prompt here",
  "thread_id": "optional-conversation-identifier"
}
```

**Response:**
```json
{
  "response": "AI-generated response text",
  "thread_id": "same-as-request-or-generated",
  "model_used": "gemini-2.5-flash",
  "cached": false,
  "security_notes": ["note1", "note2"],
  "processing_time_ms": 1234.56
}
```

### Health Check

```
GET /health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "environment": "production",
  "checks": {
    "agent": true,
    "security": true,
    "cache": true
  }
}
```

### Metrics

```
GET /metrics
```

Returns Prometheus-formatted metrics for monitoring.

**Response:**
```json
{
  "uptime_seconds": 3600.5,
  "total_requests": 1245,
  "error_count": 3,
  "cache_hit_count": 432,
  "cache_miss_count": 813,
  "average_latency_ms": 245.7,
  "total_input_tokens": 12450,
  "total_output_tokens": 98760
}
```

### Cache Statistics

```
GET /cache/stats
```

Returns cache performance statistics.

**Response:**
```json
{
  "hits": 432,
  "misses": 813,
  "hit_rate": 0.347,
  "size": 125,
  "max_size": 1000
}
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GOOGLE_API_KEY` | Google Gemini API key | - | Yes |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `true` | No |
| `LANGCHAIN_API_KEY` | LangSmith API key | - | Yes (if tracing enabled) |
| `LANGCHAIN_PROJECT` | LangSmith project name | `production-api` | No |
| `APP_ENV` | Application environment (`development`/`production`) | `development` | No |
| `LOG_LEVEL` | Logging level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `INFO` | No |
| `RATE_LIMIT` | Rate limit format (e.g., `20/minute`) | `20/minute` | No |
| `CACHE_TTL_SECONDS` | Cache time-to-live in seconds | `300` | No |
| `MAX_RETRIES` | Maximum retry attempts for failed operations | `3` | No |

## Security Features

The API implements multiple layers of security:

1. **Input Validation**: Checks for prompt injection attempts and malicious content
2. **PII Masking**: Automatically detects and masks personally identifiable information
3. **Output Validation**: Validates AI-generated responses for safety
4. **Rate Limiting**: Prevents abuse and brute-force attacks
5. **CORS Configuration**: Configurable cross-origin resource sharing

## Monitoring & Observability

### LangSmith Tracing
All LLM calls are automatically traced to LangSmith when `LANGCHAIN_TRACING_V2=true` is set. Traces include:
- Token usage
- Latency measurements
- Input/output content
- Custom tags and metadata

### Metrics Endpoint
The `/metrics` endpoint provides:
- Request counters (total, errors, cache hits/misses)
- Latency histograms
- Token consumption metrics
- Service uptime

### Health Checks
- `/health` endpoint for container orchestration
- Docker healthcheck configured in `docker-compose.yml`
- Startup/shutdown event logging

## Development Guidelines

### Code Structure
- `app/main.py`: FastAPI application setup and endpoints
- `app/agent.py`: LangGraph agent implementation
- `app/cache.py`: In-memory caching layer
- `app/config.py`: Environment configuration management
- `app/models.py`: Pydantic models for request/response validation
- `app/monitoring.py`: Metrics collection and logging utilities
- `app/security.py`: Input/output security pipeline
- `app/__init__.py`: Package initializer

### Adding New Features
1. Extend the `ProductionAgent` class in `app/agent.py` for new capabilities
2. Add new Pydantic models in `app/models.py` for new endpoints
3. Register new routes in `app/main.py`
4. Update security policies in `app/security.py` as needed
5. Add metrics collection points in `app/monitoring.py`

## Testing

Run the test suite:
```bash
pytest tests/
```

## Deployment Considerations

### Scaling
- The application is stateless except for the in-memory cache
- For horizontal scaling, consider replacing the in-memory cache with Redis
- Multiple instances can be deployed behind a load balancer

### Production Recommendations
1. Use a managed PostgreSQL database for persistent caching if needed
2. Enable HTTPS termination at the reverse proxy level
3. Set appropriate resource limits in container orchestration
4. Configure log aggregation (ELK stack, Loki, etc.)
5. Set up alerting on error rates and latency metrics

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Google Gemini](https://ai.google.dev/)
- Observability via [LangSmith](https://smith.langchain.com/)
- Containerized with Docker