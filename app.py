import os
import time
import gradio as gr
from graph_engine import (
    SESSION_LOG_FILE,
    get_mermaid_diagram,
    run_initial_pipeline,
    run_revision_step,
)


def generate_brief_action(product_name, category, audience):
  yield (
      "🤖 *Step 1/4: LangGraph executing agent pipeline (Generator ➔ Critique ➔ Refiner ➔ Validator)...*",
      "⏳ Analyzing...",
      [
          ["Generator Latency", "Running...", "Node 1"],
          ["Critique Latency", "Pending...", "Node 2"],
          ["Refiner Latency", "Pending...", "Node 3"],
          ["Prompt Tokens", "-", "API Usage"],
          ["Completion Tokens", "-", "API Usage"],
          ["Grand Total Tokens", "-", "Combined"],
          ["Estimated Cost", "-", "Calculated"],
      ],
      gr.update(choices=[], value=None),
      None,
      gr.update(visible=False),
  )

  state = run_initial_pipeline(product_name, category, audience)

  if state.get("error_message"):
    yield (
        f"❌ Error: {state['error_message']}",
        "❌ Validation Failed",
        [["-", "-", "-"]],
        gr.update(choices=[], value=None),
        state,
        gr.update(visible=False),
    )
    return

  history = state.get("history", [])
  latest_version = history[-1] if history else {}

  markdown_output = latest_version.get("pitch", "")
  latencies = state.get("node_latencies", {})
  is_valid = latest_version.get("is_valid", False)
  retries = state.get("retry_count", 1)

  prompt_tokens = int(latest_version.get("prompt_tokens", 0))
  completion_tokens = int(latest_version.get("completion_tokens", 0))
  total_tokens = prompt_tokens + completion_tokens
  est_cost = float(latest_version.get("estimated_cost", 0.0))

  validation_badge = (
      f"✅ **Validation Passed (Retries: {retries}):** Structure, Markdown"
      " Table, Critique Review & Call-to-Action Verified"
      if is_valid
      else "⚠️ **Validation Warning:** Output structure check incomplete"
  )

  telemetry_data = [
      ["Generator Latency", f"{latencies.get('generator', 0)}s", "Node 1"],
      ["Critique Latency", f"{latencies.get('critique', 0)}s", "Node 2"],
      ["Refiner Latency", f"{latencies.get('refiner', 0)}s", "Node 3"],
      ["Prompt Tokens", f"{prompt_tokens:,}", "API Usage"],
      ["Completion Tokens", f"{completion_tokens:,}", "API Usage"],
      ["Grand Total Tokens", f"{total_tokens:,}", "Combined"],
      ["Estimated Cost", f"${est_cost:.5f}", "Calculated"],
  ]

  version_choices = [v["version_name"] for v in history]
  selected_version_name = version_choices[-1] if version_choices else None

  streamed_text = ""
  for chunk in markdown_output.split("\n"):
    streamed_text += chunk + "\n"
    yield (
        streamed_text,
        validation_badge,
        telemetry_data,
        gr.update(choices=version_choices, value=selected_version_name),
        state,
        gr.update(visible=False),
    )
    time.sleep(0.01)

  yield (
      markdown_output,
      validation_badge,
      telemetry_data,
      gr.update(choices=version_choices, value=selected_version_name),
      state,
      gr.update(visible=True),
  )


def revise_brief_action(current_state, feedback):
  if not current_state:
    return (
        "No state found.",
        "❌ Validation Failed",
        [["-", "-", "-"]],
        gr.update(choices=[], value=None),
        current_state,
    )

  updated_state = run_revision_step(current_state, feedback)
  history = updated_state.get("history", [])
  latest_version = history[-1] if history else {}

  markdown_output = latest_version.get("pitch", "")
  latencies = updated_state.get("node_latencies", {})
  is_valid = latest_version.get("is_valid", False)

  prompt_tokens = int(latest_version.get("prompt_tokens", 0))
  completion_tokens = int(latest_version.get("completion_tokens", 0))
  total_tokens = prompt_tokens + completion_tokens
  est_cost = float(latest_version.get("estimated_cost", 0.0))

  validation_badge = (
      "✅ **Validation Passed (Revised):** Structure and formatting verified"
      if is_valid
      else "⚠️ **Validation Warning:** Revision structure check incomplete"
  )

  telemetry_data = [
      ["Generator Latency", f"{latencies.get('generator', 0)}s", "Node 1"],
      ["Critique Latency", f"{latencies.get('critique', 0)}s", "Node 2"],
      ["Refiner Latency", f"{latencies.get('refiner', 0)}s", "Node 3"],
      ["Prompt Tokens", f"{prompt_tokens:,}", "API Usage"],
      ["Completion Tokens", f"{completion_tokens:,}", "API Usage"],
      ["Grand Total Tokens", f"{total_tokens:,}", "Combined"],
      ["Estimated Cost", f"${est_cost:.5f}", "Calculated"],
  ]

  version_choices = [v["version_name"] for v in history]
  selected_version_name = version_choices[-1] if version_choices else None

  return (
      markdown_output,
      validation_badge,
      telemetry_data,
      gr.update(choices=version_choices, value=selected_version_name),
      updated_state,
  )


def switch_version_action(current_state, chosen_version_name):
  if not current_state or not chosen_version_name:
    return gr.update(), gr.update(), gr.update()

  history = current_state.get("history", [])
  target_version = next(
      (v for v in history if v["version_name"] == chosen_version_name), None
  )

  if not target_version:
    return gr.update(), gr.update(), gr.update()

  markdown_output = target_version.get("pitch", "")
  latencies = current_state.get("node_latencies", {})
  is_valid = target_version.get("is_valid", False)

  prompt_tokens = int(target_version.get("prompt_tokens", 0))
  completion_tokens = int(target_version.get("completion_tokens", 0))
  total_tokens = prompt_tokens + completion_tokens
  est_cost = float(target_version.get("estimated_cost", 0.0))

  validation_badge = (
      f"📂 **Viewing Version: {chosen_version_name}**"
      if is_valid
      else "⚠️ **Viewing Version (Warning):** Structure check incomplete"
  )

  telemetry_data = [
      ["Generator Latency", f"{latencies.get('generator', 0)}s", "Node 1"],
      ["Critique Latency", f"{latencies.get('critique', 0)}s", "Node 2"],
      ["Refiner Latency", f"{latencies.get('refiner', 0)}s", "Node 3"],
      ["Prompt Tokens", f"{prompt_tokens:,}", "API Usage"],
      ["Completion Tokens", f"{completion_tokens:,}", "API Usage"],
      ["Grand Total Tokens", f"{total_tokens:,}", "Combined"],
      ["Estimated Cost", f"${est_cost:.5f}", "Calculated"],
  ]

  return markdown_output, validation_badge, telemetry_data


def export_file_action(current_state, chosen_version_name):
  if not current_state:
    return None, gr.update(visible=False)

  history = current_state.get("history", [])
  target_version = next(
      (v for v in history if v["version_name"] == chosen_version_name),
      history[-1] if history else None,
  )

  if not target_version or not target_version.get("pitch"):
    return None, gr.update(visible=False)

  product_name = (
      current_state.get("product_name", "product").replace(" ", "_").lower()
  )
  v_tag = (
      chosen_version_name.split()[0].lower() if chosen_version_name else "v1"
  )
  filename = f"{product_name}_{v_tag}_brief.md"

  with open(filename, "w", encoding="utf-8") as f:
    f.write(
        f"# Marketing Pitch Brief ({chosen_version_name}):"
        f" {current_state.get('product_name')}\n\n"
    )
    f.write(target_version["pitch"])

  return filename, gr.update(visible=True)


def export_session_logs_action():
  if os.path.exists(SESSION_LOG_FILE):
    return SESSION_LOG_FILE, gr.update(visible=True)
  return None, gr.update(visible=False)


# ==========================================
# GRADIO BLOCKS INTERFACE
# ==========================================
with gr.Blocks(title="AI Marketing Brief Agent") as demo:
  state_store = gr.State()

  with gr.Row():
    gr.Markdown("# 🚀 AI Agent Marketing Brief Generator")
    export_logs_btn = gr.Button("📊 Export Session Logs", size="sm")

  logs_download = gr.File(label="Download Session Logs JSON", visible=False)

  # --- LANGGRAPH ARCHITECTURE VISUALIZER ACCORDION ---
  with gr.Accordion(
      "📊 Live LangGraph Architecture & State Machine Diagram", open=False
  ):
    gr.Markdown(
        "Below is the live Mermaid.js execution graph showing the multi-agent"
        " workflow and automatic validation retry loops:"
    )
    mermaid_syntax = get_mermaid_diagram()
    # Render interactive Mermaid.js diagram directly via HTML & CDN
    gr.HTML(f"""
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({{ startOnLoad: true }});</script>
        <div class="mermaid" style="background: white; padding: 20px; border-radius: 8px; text-align: center;">
            {mermaid_syntax}
        </div>
    """)

  with gr.Row():
    with gr.Column(scale=1):
      gr.Markdown("### 📝 Product Information")

      gr.Markdown(
          "<p style='font-size: 12px; color: #666; margin-bottom: 4px;'>⚡"
          " Quick-Select Presets:</p>"
      )
      with gr.Row():
        btn_ecosip = gr.Button("💧 EcoSip Bottle", size="sm")
        btn_copilot = gr.Button("🤖 AI Copilot", size="sm")
        btn_watch = gr.Button("⌚ Smart Watch", size="sm")

      product_name = gr.Textbox(label="Product Name", value="EcoSip")
      category = gr.Textbox(
          label="Category", value="Reusable Smart Water Bottle"
      )
      audience = gr.Textbox(
          label="Target Audience", value="Eco-conscious fitness enthusiasts"
      )

      generate_btn = gr.Button(
          "🚀 Generate Marketing Brief", variant="primary", size="lg"
      )
      gr.Markdown(
          "<p style='text-align: center; color: #666; font-size: 13px;"
          " margin-top: 4px;'>👆 Click this button to run the agent pipeline</p>"
      )

    with gr.Column(scale=1):
      gr.Markdown("### 📊 Pipeline Telemetry")
      telemetry_table = gr.DataFrame(
          headers=["Metric", "Value", "Context"],
          value=[
              ["Generator Latency", "-", "-"],
              ["Critique Latency", "-", "-"],
              ["Refiner Latency", "-", "-"],
              ["Prompt Tokens", "-", "-"],
              ["Completion Tokens", "-", "-"],
              ["Grand Total Tokens", "-", "-"],
              ["Estimated Cost", "-", "-"],
          ],
          interactive=False,
          label="Performance & Token Metrics",
      )

  btn_ecosip.click(
      lambda: (
          "EcoSip",
          "Reusable Smart Water Bottle",
          "Eco-conscious fitness enthusiasts",
      ),
      outputs=[product_name, category, audience],
  )
  btn_copilot.click(
      lambda: (
          "DevFlow AI",
          "Developer Productivity Tool",
          "Software Engineers and DevOps Teams",
      ),
      outputs=[product_name, category, audience],
  )
  btn_watch.click(
      lambda: (
          "AuraPulse",
          "Wearable Health Monitor",
          "Health-conscious professionals and athletes",
      ),
      outputs=[product_name, category, audience],
  )

  gr.HTML(
      "<hr style='margin: 25px 0; border: none; border-top: 1px solid #ccc;'>"
  )

  with gr.Row():
    with gr.Column(scale=3):
      gr.Markdown("### 📄 Complete Marketing Brief & Asset Details")
    with gr.Column(scale=2):
      version_dropdown = gr.Dropdown(
          label="📜 Version History & Rollback",
          choices=[],
          interactive=True,
          value=None,
      )

  validation_status = gr.Markdown("*Validation status will appear here...*")
  output_markdown = gr.Markdown(
      "Detailed sections, feature tables, and strategies will stream here..."
  )

  with gr.Column(visible=False) as hitl_group:
    gr.HTML(
        "<hr"
        " style='margin: 20px 0; border: none; border-top: 1px solid #ddd;'>"
    )
    gr.Markdown("### ⏸️ Human-in-the-Loop Feedback & Approval")
    feedback_input = gr.Textbox(
        label="Revision Instructions",
        placeholder=(
            "e.g., Make the feature table more concise or emphasize eco-friendly"
            " stats."
        ),
    )
    with gr.Row():
      revise_btn = gr.Button("🔄 Request Revision", variant="secondary")
      export_btn = gr.Button("📁 Export & Download Markdown", variant="primary")

    file_download = gr.File(
        label="Downloadable Markdown Brief", visible=False
    )

  # --- EVENT BINDINGS ---
  generate_btn.click(
      fn=generate_brief_action,
      inputs=[product_name, category, audience],
      outputs=[
          output_markdown,
          validation_status,
          telemetry_table,
          version_dropdown,
          state_store,
      ],
  ).then(
      lambda state: gr.update(visible=True)
      if state and state.get("history")
      else gr.update(visible=False),
      inputs=[state_store],
      outputs=[hitl_group],
  )

  revise_btn.click(
      fn=revise_brief_action,
      inputs=[state_store, feedback_input],
      outputs=[
          output_markdown,
          validation_status,
          telemetry_table,
          version_dropdown,
          state_store,
      ],
  )

  version_dropdown.change(
      fn=switch_version_action,
      inputs=[state_store, version_dropdown],
      outputs=[output_markdown, validation_status, telemetry_table],
  )

  export_btn.click(
      fn=export_file_action,
      inputs=[state_store, version_dropdown],
      outputs=[file_download, file_download],
  )

  export_logs_btn.click(
      fn=export_session_logs_action, outputs=[logs_download, logs_download]
  )

if __name__ == "__main__":
  demo.launch(theme=gr.themes.Soft())