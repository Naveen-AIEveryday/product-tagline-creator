import json
import os
import re
import time
from typing import TypedDict
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

load_dotenv()

SESSION_LOG_FILE = "session_logs.json"

base_url = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://api.ollama.com/v1")
model_name = os.getenv("OLLAMA_CLOUD_MODEL", "gpt-oss:20b")
api_key = os.getenv("OLLAMA_CLOUD_API_KEY", "ollama")

model = ChatOpenAI(
    model=model_name,
    openai_api_key=api_key,
    openai_api_base=base_url,
    temperature=0.7,
)


class AgentState(TypedDict):
  product_name: str
  category: str
  audience: str
  draft_pitch: str
  critique_notes: str
  final_pitch: str
  is_valid: bool
  retry_count: int
  error_message: str
  total_prompt_tokens: int
  total_completion_tokens: int
  estimated_cost: float
  node_latencies: dict
  history: list
  human_decision: str
  human_feedback: str


def extract_metrics(response, start_time):
  elapsed_time = round(time.time() - start_time, 2)
  usage = getattr(response, "response_metadata", {}).get("token_usage", {})
  prompt_tokens = usage.get("prompt_tokens", 0)
  completion_tokens = usage.get("completion_tokens", 0)
  return prompt_tokens, completion_tokens, elapsed_time


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
  input_cost_per_token = 2.00 / 1_000_000
  output_cost_per_token = 10.00 / 1_000_000
  cost = (prompt_tokens * input_cost_per_token) + (
      completion_tokens * output_cost_per_token
  )
  return round(cost, 5)


def log_session_to_file(state: dict):
  log_entry = {
      "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
      "product_name": state.get("product_name"),
      "category": state.get("category"),
      "audience": state.get("audience"),
      "total_prompt_tokens": state.get("total_prompt_tokens"),
      "total_completion_tokens": state.get("total_completion_tokens"),
      "estimated_cost": state.get("estimated_cost"),
      "node_latencies": state.get("node_latencies"),
      "is_valid": state.get("is_valid"),
      "versions_count": len(state.get("history", [])),
  }

  logs = []
  if os.path.exists(SESSION_LOG_FILE):
    try:
      with open(SESSION_LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
    except Exception:
      logs = []

  logs.append(log_entry)
  with open(SESSION_LOG_FILE, "w", encoding="utf-8") as f:
    json.dump(logs, f, indent=4)


def generate_node(state: AgentState):
  start_time = time.time()
  try:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Create a catchy marketing tagline and initial concept description.",
        ),
        (
            "human",
            "Product: {product_name}, Category: {category}, Target Audience:"
            " {audience}",
        ),
    ])
    chain = prompt | model
    response = chain.invoke({
        "product_name": state["product_name"],
        "category": state["category"],
        "audience": state["audience"],
    })
    p_tokens, c_tokens, latency = extract_metrics(response, start_time)

    return {
        "draft_pitch": response.content,
        "error_message": "",
        "total_prompt_tokens": p_tokens,
        "total_completion_tokens": c_tokens,
        "node_latencies": {"generator": latency},
    }
  except Exception as e:
    return {"error_message": str(e)}


def critique_node(state: AgentState):
  start_time = time.time()
  try:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            (
                "You are an expert Creative Director. Analyze the draft pitch"
                " for tone consistency, psychological appeal to the target"
                " audience, and marketing depth. Provide constructive critique"
                " notes to enhance the final brief."
            ),
        ),
        (
            "human",
            (
                "Product: {product_name}\nTarget Audience:"
                " {audience}\nDraft:\n{draft_pitch}"
            ),
        ),
    ])
    chain = prompt | model
    response = chain.invoke({
        "product_name": state["product_name"],
        "audience": state["audience"],
        "draft_pitch": state.get("draft_pitch", ""),
    })
    p_tokens, c_tokens, latency = extract_metrics(response, start_time)

    total_p = state.get("total_prompt_tokens", 0) + p_tokens
    total_c = state.get("total_completion_tokens", 0) + c_tokens

    latencies = state.get("node_latencies", {})
    latencies["critique"] = latency

    return {
        "critique_notes": response.content,
        "total_prompt_tokens": total_p,
        "total_completion_tokens": total_c,
        "node_latencies": latencies,
    }
  except Exception as e:
    return {"error_message": str(e)}


def refiner_node(state: AgentState):
  start_time = time.time()
  retry = state.get("retry_count", 0) + 1

  feedback_instruction = ""
  if state.get("human_decision") == "revise" and state.get("human_feedback"):
    feedback_instruction = (
        f"\nIMPORTANT - Incorporate human feedback: {state['human_feedback']}"
    )
  elif not state.get("is_valid", True) and retry > 1:
    feedback_instruction = (
        "\nWARNING: Previous output failed validation check! Ensure strict"
        " adherence to Markdown headings (#, ##), standard pipe tables (| and"
        " ---), and a clear Call to Action section."
    )

  try:
    system_content = (
        "You are a master copywriter. Convert the draft pitch and Creative"
        " Director critique notes into a complete marketing brief formatted"
        " strictly in clean Markdown.\nCRITICAL FORMATTING RULES:\n1. Use clear"
        " Markdown headings (#, ##).\n2. For the Feature Table, you MUST use"
        " standard Markdown table syntax with pipes (|) and hyphens (---). Do"
        " NOT use HTML tags.\n3. Ensure every table row is on its own separate"
        " line.\n\nInclude these exact sections:\n1. Tagline\n2. Elevator"
        " Pitch\n3. 'Why It Wins' Feature Table (Columns: Feature | Benefit |"
        " Impact)\n4. Core Value Proposition\n5. Call to Action"
    )
    if state.get("critique_notes"):
      system_content += f"\n\nDirector Critique Notes to Apply:\n{state['critique_notes']}"
    if feedback_instruction:
      system_content += f"\n{feedback_instruction}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_content),
        ("human", "Draft Pitch:\n{draft_pitch}"),
    ])

    chain = prompt | model
    response = chain.invoke({"draft_pitch": state.get("draft_pitch", "")})
    p_tokens, c_tokens, latency = extract_metrics(response, start_time)

    total_p = state.get("total_prompt_tokens", 0) + p_tokens
    total_c = state.get("total_completion_tokens", 0) + c_tokens
    est_cost = calculate_cost(total_p, total_c)

    latencies = state.get("node_latencies", {})
    latencies["refiner"] = latency

    return {
        "final_pitch": response.content,
        "retry_count": retry,
        "error_message": "",
        "total_prompt_tokens": total_p,
        "total_completion_tokens": total_c,
        "estimated_cost": est_cost,
        "node_latencies": latencies,
        "human_decision": "",
        "human_feedback": "",
    }
  except Exception as e:
    return {"error_message": str(e)}


def validator_node(state: AgentState):
  if state.get("error_message"):
    return {"is_valid": False}

  pitch = state.get("final_pitch", "")
  has_tagline = bool(
      re.search(r"Tagline", pitch, re.IGNORECASE)
      or re.search(r"^\*", pitch, re.MULTILINE)
  )
  has_table = "|" in pitch and "---" in pitch
  has_cta = bool(re.search(r"Call to Action", pitch, re.IGNORECASE))

  return {"is_valid": has_tagline and has_table and has_cta}


# --- BUILD COMPILED LANGGRAPH STATE MACHINE ---
workflow = StateGraph(AgentState)
workflow.add_node("generator", generate_node)
workflow.add_node("critique", critique_node)
workflow.add_node("refiner", refiner_node)
workflow.add_node("validator", validator_node)

workflow.set_entry_point("generator")
workflow.add_edge("generator", "critique")
workflow.add_edge("critique", "refiner")
workflow.add_edge("refiner", "validator")


def should_retry(state: AgentState):
  # Automatic retry loop if validation fails and retry count is under 2
  if not state.get("is_valid", False) and state.get("retry_count", 0) < 2:
    return "retry"
  return "end"


workflow.add_conditional_edges(
    "validator",
    should_retry,
    {
        "retry": "refiner",
        "end": END,
    },
)

app_graph = workflow.compile()


def get_mermaid_diagram():
  try:
    mermaid_code = app_graph.get_graph().draw_mermaid()
    # Strip out the complex frontmatter config lines that cause messy rendering
    if "---" in mermaid_code:
      parts = mermaid_code.split("---")
      if len(parts) >= 3:
        mermaid_code = parts[2].strip()

    # Ensure clean flowchart declaration
    if not mermaid_code.startswith("graph"):
      mermaid_code = "graph TD;\n" + mermaid_code

    return mermaid_code
  except Exception:
    return (
        "graph TD;\n  generator --> critique;\n  critique --> refiner;\n "
        " refiner --> validator;\n  validator -- retry --> refiner;\n "
        " validator -- end --> END;"
    )    


def run_initial_pipeline(product_name: str, category: str, audience: str):
  initial_inputs = {
      "product_name": product_name,
      "category": category,
      "audience": audience,
      "error_message": "",
      "total_prompt_tokens": 0,
      "total_completion_tokens": 0,
      "estimated_cost": 0.0,
      "node_latencies": {},
      "human_decision": "",
      "human_feedback": "",
      "is_valid": False,
      "retry_count": 0,
      "critique_notes": "",
      "history": [],
  }

  # Execute compiled graph state machine
  final_state = app_graph.invoke(initial_inputs)

  version_entry = {
      "version_name": "v1 - Initial Brief",
      "pitch": final_state.get("final_pitch", ""),
      "latencies": final_state.get("node_latencies", {}),
      "prompt_tokens": final_state.get("total_prompt_tokens", 0),
      "completion_tokens": final_state.get("total_completion_tokens", 0),
      "estimated_cost": final_state.get("estimated_cost", 0.0),
      "is_valid": final_state.get("is_valid", False),
  }
  final_state["history"] = [version_entry]

  log_session_to_file(final_state)
  return final_state


def run_revision_step(current_state: dict, feedback: str):
  updated_input = {
      **current_state,
      "human_decision": "revise",
      "human_feedback": feedback,
  }

  # Run revision through refiner and validator
  refin_res = refiner_node(updated_input)
  val_res = validator_node({**updated_input, **refin_res})
  combined = {**updated_input, **refin_res, **val_res}

  history = combined.get("history", [])
  next_v_num = len(history) + 1
  version_entry = {
      "version_name": f"v{next_v_num} - Revision ({feedback[:20]}...)",
      "pitch": combined["final_pitch"],
      "latencies": combined["node_latencies"],
      "prompt_tokens": combined["total_prompt_tokens"],
      "completion_tokens": combined["total_completion_tokens"],
      "estimated_cost": combined["estimated_cost"],
      "is_valid": combined["is_valid"],
  }
  history.append(version_entry)
  combined["history"] = history

  log_session_to_file(combined)
  return combined 