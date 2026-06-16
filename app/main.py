

import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langsmith import traceable
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.agent import ProductionAgent
from app.cache import ResponseCache
from app.config import get_settings
from app.models import (ChatRequest, ChatResponse, ErrorResponse,
                        HealthResponse, MetricsResponse)
from app.monitoring import MetricsCollector, RequestTimer, get_logger
from app.security import SecurityPipeline

load_dotenv()

logger = get_logger(name="Rag Production")

# === Lifespan (startup/shutdown) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
  """ Initialize all components on startup and shutdown on shutdown. """
  global security, cache, metrics, agent
  
  settings = get_settings()
  
  logger.info("Starting production API...", extra={"extra_env": {
    "environment": settings.app_env,
    "primary_model": settings.primary_model,
    "tracing_enabled": settings.langchain_tracing_v2,
  }})
  
  # Initialize the security pipeline
  security = SecurityPipeline()
  
  # Initialize the response cache
  cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
  
  # Initialize the metrics collector
  metrics = MetricsCollector()
  
  # Initialize the agent
  agent = ProductionAgent()
  
  logger.info("All components initialized. Ready to serve requests...")
  
  yield
  
  # Shutdown
  logger.info("Shutting down production API...", extra=metrics.summary)
  
  
# === Rate Limiter Setup ===
limiter = Limiter(key_func=get_remote_address)

# === FastAPI Setup ===
app = FastAPI(
  title="Production LangGraph API",
  description="A production-ready LangGraph API for use with LangSmith's LangGraph AI, caching, and observability. For more information, see https://github.com/langsmith-dev/langgraph-ai.",
  version="1.0.0",
  lifespan=lifespan
)

app.state.limiter = limiter


# === Exception Handlers ===
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
  return JSONResponse(
    status_code=429,
    content=ErrorResponse(error="Rate limit exceeded.").model_dump()
  )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
  return JSONResponse(
    status_code=exc.status_code,
    content=ErrorResponse(error=exc.detail).model_dump()
  )
  
  
# === Middleware ===
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
  

@app.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().rate_limit)
@traceable(name="chat_endpoint")
async def chat(request: Request, body: ChatRequest):
  """
  Main chat endpoint.
  
  Flow:
  1. Security check (injection + PII masking)
  2. Cache lookup
  3. LangGraph agen invoke (if not cached)
  4. Output validation
  5. Cache store
  6. Return response
  """
  with RequestTimer() as timer:
    security_notes = []
    
    # ---- Step 1: Security Check ----
    is_allowed, cleaned_message, notes = security.check_input(body.message)
    security_notes.extend(notes)
    
    if not is_allowed:
      logger.warning("Request blocked by security", extra={
        "extra_data": {
          "reasong": notes,
          "thread_id": body.thread_id,
        }
      })
      metrics.record_request(latency_ms=0, is_error=True)
      raise HTTPException(status_code=403, detail="Request blocked by security")
    
    # ---- Step 2: Cache Lookup ----
    cached_response = cache.get(cleaned_message)
    if cached_response is not None:
      metrics.record_request(latency_ms=0, cache_hit=True)
      logger.info("Cache hit", extra={
        "extra_data": {
          "thread_id": body.thread_id,
        }
      })
      
      return ChatResponse(
        response=cached_response,
        thread_id=body.thread_id,
        model_used="cache",
        cached=True,
        processing_time_ms=0
      )
      
    
    # ---- Step 3: Invoke LangGraph Agent ----
    try:
      result = agent.process(cleaned_message)
      
    except Exception as e:
      logger.error("Error invoking LangGraph agent", extra={
        "extra_data": {
          "error": str(e),
          "thread_id": body.thread_id,
        }
      })
      metrics.record_request(latency_ms=0, is_error=True)
      raise HTTPException(status_code=500, detail="Error invoking LangGraph agent")
    
    
    response_text = result["response"]
    model_used = result["model_used"]
    
    # ---- Step 4: Output Validation ----
    validated_response, output_warnings = security.check_output(response_text)
    security_notes.extend(output_warnings)
    
    
    # ---- Step 5: Cache Store ----
    cache.set(cleaned_message, validated_response)
    
  # ---- Step 6: Log & Record Metrics ----
  input_tokens = int(len(cleaned_message.split()) * 1.3)
  output_tokens = int(len(validated_response.split()) * 1.3)
  
  metrics.record_request(
    latency_ms=timer.elapsed,
    tokens_input=input_tokens,
    tokens_output=output_tokens,
    cache_hit=False
  )
  
  if security_notes:
    logger.info("Security notes", extra={
      "extra_data": {
        "notes": security_notes,
        "thread_id": body.thread_id,
      }
    })
    
    
  logger.info("Response generated", extra={
    "extra_data": {
      "thread_id": body.thread_id,
      "model_used": model_used,
    }
  })
  
  return ChatResponse(
    response=validated_response,
    thread_id=body.thread_id,
    model_used=model_used,
    security_notes=security_notes,
    cached=False,
    processing_time_ms=round(timer.elapsed, 2)
  )
  

@app.get("/health", response_model=HealthResponse)
async def health():
  """Health check for Docker"""
  settings = get_settings()
  
  checks = {
    "agent": agent is not None,
    "security": security is not None,
    "cache": cache is not None,
  }
  
  all_healthy = all(checks.values())
  
  return HealthResponse(
    status="healthy" if all_healthy else "unhealthy",
    environment=settings.app_env, 
    checks=checks
  )
  

@app.get("/metrics", response_model=MetricsResponse)
async def metrics():
  """Metrics for monitoring dashnoards."""
  summary = metrics.summary
  
  return MetricsResponse(**summary)


@app.get("/cache/stats")
async def cache_stats():
  """Cache performance statistics."""
  return cache.stats()