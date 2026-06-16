


from typing import Optional
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable
import os


from app.config import get_settings


class AgentState(TypedDict):
  """
  State for the production agent.
  Uses Annotated with add_messages reducer for message accumulation.
  """
  
  messages: Annotated[list[BaseMessage], add_messages]
  error: Optional[str]
  retry_count: int
  model_used: str
  

class ProductionAgent:
  """
  Production LangGraph agent with:
  - Retry on failure (model fallback)
  - Graceful error handling
  - LangSmith tracing
  """
  
  def __init__(self):
    settings = get_settings()
    
    # Push tracing config into the actual environment so LangChain sees it
    os.environ["LANGCHAIN_TRACING_V2"] = str(settings.langchain_tracing_v2).lower()  # "true" / "false"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    
    self.primary_llm = GoogleGenerativeAI(
      model=settings.primary_model,
      temperature=0,
      timeout=30,
      max_retries=0,
      api_key=settings.google_api_key
    )
    
    self.fallback_llm = GoogleGenerativeAI(
      model=settings.fallback_model,
      temperature=0,
      timeout=30,
      max_retries=0,
      api_key=settings.google_api_key
    )
    self.max_retries = settings.max_retries
    self.graph = self._build_graph()
  
  
  def _build_graph(self):
    """Build the langGraph state machine."""
    
    def process_message(state: AgentState) -> dict:
      """Try to process the message with the primary model."""
      
      try:
        response = self.primary_llm.invoke(state['messages'])
        return {
          "messages": [response],
          "error": None,
          "model_used": "primary",
        }
        
      except Exception as e:
        return {
          "retry_count": state['retry_count'] + 1,
          "error": str(e),
          "model_used": "",
        }
        
    def try_fallback(state: AgentState) -> dict:
      """Fallback to secondary model."""
      
      try:
        response = self.fallback_llm.invoke(state['messages'])
        return {
          "messages": [response],
          "error": None,
          "model_used": "fallback",
        }
        
      except Exception as e:
        return {
          "error": str(e),
          "model_used": "",
        }
        
    def handle_error(state: AgentState) -> dict:
      """Return a graceful error message."""
      
      return {
        "messages": [
          AIMessage(content=(
            "Sorry, I'm having trouble understanding your request. "
            "Please try again later."
          ))
        ],
        "model_used": "error_handler",
        
      }
      
    def route_after_process(state: AgentState) -> str:
      """Decide what to do after primary model attempt."""
      
      if state.get("error") is None:
        return "done"
      elif state["retry_count"] < self.max_retries:
        return "fallback"
      else:
        return "error"
      
    def route_after_fallback(state: AgentState) -> str:
      """Decide what to do after fallback model attempt."""
      
      if state.get("error") is None:
        return "done"
      else:
        return "error"
      
    # Build the graph
    graph = StateGraph(AgentState)
    
    
    graph.add_node("process", process_message)
    graph.add_node("fallback", try_fallback)
    graph.add_node("error", handle_error)
    
    graph.add_edge(START, "process")
    graph.add_conditional_edges(
      "process",
      route_after_process,
      {
        "done": END,
        "fallback": "fallback",
        "error": "error",
      }
    )
    
    graph.add_conditional_edges(
      "fallback",
      route_after_fallback,
      {
        "done": END,
        "error": "error",
      }
    )
    
    graph.add_edge("error", END)
    
    return graph.compile()
  
  @traceable(name="production_agent_invoke")
  def process(self, message: str) -> dict:
    """
    Invoke the agent with a user message.
    Returns: {"response": str, "model_used": str, "error": str | None}
    """
    
    result = self.graph.invoke({
      "messages": [HumanMessage(content=message)],
      "retry_count": 0,
      "error": None,
      "model_used": "",
    })
    
    return {
      "response": result["messages"][-1].content,
      "model_used": result.get("model_used", "unknown"),
      "error": result.get("error"),
    }
    