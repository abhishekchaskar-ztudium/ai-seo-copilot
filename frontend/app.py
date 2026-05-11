from __future__ import annotations

import os
from collections import Counter
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DATASET_OPTIONS = {
    "Organic keywords": "organic_keywords",
    "Top pages": "top_pages",
    "Backlinks": "backlinks",
    "Broken backlinks": "broken_backlinks",
    "Competitors": "competitors",
}
MODEL_OPTIONS = [
    "gemini-2.5-flash - Recommended",
    "gemini-2.5-pro - Best quality",
    "gemini-2.5-flash-lite - Fastest / cheapest",
    "gemini-2.0-flash - Fallback",
    "custom",
]
MODEL_CODES = {
    "gemini-2.5-flash - Recommended": "gemini-2.5-flash",
    "gemini-2.5-pro - Best quality": "gemini-2.5-pro",
    "gemini-2.5-flash-lite - Fastest / cheapest": "gemini-2.5-flash-lite",
    "gemini-2.0-flash - Fallback": "gemini-2.0-flash",
}


st.set_page_config(page_title="AI SEO Copilot", layout="wide")

st.markdown(
    """
    <style>
    :root {
      --bg: #0b1118;
      --panel: #111a24;
      --panel-2: #162232;
      --line: #263648;
      --text: #eef5ff;
      --muted: #95a5b8;
      --accent: #26d0a8;
      --accent-2: #58a6ff;
      --warn: #ffbf69;
    }
    .stApp {
      background:
        radial-gradient(circle at top left, rgba(38, 208, 168, 0.12), transparent 30rem),
        linear-gradient(180deg, #0b1118 0%, #0d141d 100%);
      color: var(--text);
    }
    [data-testid="stSidebar"] {
      background: #0c131c;
      border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
      color: var(--text);
    }
    .block-container {
      padding-top: 1.5rem;
      max-width: 1440px;
    }
    .dashboard-hero {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.1rem 1.25rem;
      border: 1px solid var(--line);
      background: rgba(17, 26, 36, 0.92);
      border-radius: 8px;
      margin-bottom: 1rem;
    }
    .dashboard-title {
      font-size: 1.7rem;
      font-weight: 760;
      line-height: 1.15;
      letter-spacing: 0;
      margin: 0;
    }
    .dashboard-subtitle {
      color: var(--muted);
      margin-top: 0.35rem;
      font-size: 0.94rem;
      letter-spacing: 0;
    }
    .status-pill {
      border: 1px solid rgba(38, 208, 168, 0.45);
      color: #b6fff0;
      background: rgba(38, 208, 168, 0.12);
      border-radius: 999px;
      padding: 0.42rem 0.75rem;
      font-size: 0.86rem;
      white-space: nowrap;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.85rem;
      margin-bottom: 1rem;
    }
    .kpi-card {
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(22, 34, 50, 0.96), rgba(17, 26, 36, 0.96));
      border-radius: 8px;
      padding: 1rem;
      min-height: 7rem;
    }
    .kpi-label {
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0;
      margin-bottom: 0.55rem;
    }
    .kpi-value {
      color: var(--text);
      font-size: 2rem;
      line-height: 1;
      font-weight: 760;
      letter-spacing: 0;
    }
    .kpi-foot {
      color: var(--muted);
      font-size: 0.84rem;
      margin-top: 0.65rem;
    }
    .panel {
      border: 1px solid var(--line);
      background: rgba(17, 26, 36, 0.92);
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }
    .section-title {
      color: var(--text);
      font-size: 1.05rem;
      font-weight: 720;
      margin-bottom: 0.8rem;
      letter-spacing: 0;
    }
    div[data-testid="stDataFrame"] {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .stTabs [data-baseweb="tab-list"] {
      gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0e1721;
      padding: 0.5rem 0.8rem;
    }
    .stTabs [aria-selected="true"] {
      border-color: rgba(38, 208, 168, 0.75);
      color: #b6fff0;
    }
    @media (max-width: 900px) {
      .dashboard-hero {
        align-items: flex-start;
        flex-direction: column;
      }
      .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 560px) {
      .kpi-grid {
        grid-template-columns: 1fr;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_request(method: str, path: str, **kwargs: Any) -> requests.Response:
    response = requests.request(method, f"{API_BASE_URL}{path}", timeout=120, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))
    return response


def average(values: list[float], default: float = 0) -> float:
    return round(sum(values) / len(values), 2) if values else default


def task_frame(task_rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Issue": task["issue"],
                "Page": task["page"],
                "Keyword": task.get("keyword", ""),
                "Priority": task["priority_score"],
                "Confidence": task["confidence_score"],
                "Evidence": task["evidence"],
            }
            for task in task_rows
        ]
    )


with st.sidebar:
    st.header("Workspace")
    dataset_label = st.selectbox("Ahrefs export", list(DATASET_OPTIONS.keys()))
    dataset_type = DATASET_OPTIONS[dataset_label]
    files = st.file_uploader(
        "CSV files",
        type=["csv"],
        accept_multiple_files=True,
        key=dataset_type,
    )

    upload_clicked = st.button("Upload CSVs", use_container_width=True)

    st.divider()
    st.header("Gemini")
    gemini_api_key = st.text_input("API key", type="password")
    model_choice = st.selectbox("Model", MODEL_OPTIONS)
    custom_model = ""
    if model_choice == "custom":
        custom_model = st.text_input("Custom model code", placeholder="gemini-2.5-flash-preview-09-2025")
    selected_model = custom_model.strip() if model_choice == "custom" else MODEL_CODES[model_choice]

    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)
    reset_clicked = st.button("Reset", use_container_width=True)

    st.divider()
    export_format = st.radio("Export", ["json", "csv"], horizontal=True)


if upload_clicked:
    if not files:
        st.warning("Choose one or more CSV files first.")
    else:
        multipart_files = [
            ("files", (file.name, file.getvalue(), "text/csv"))
            for file in files
        ]
        try:
            response = api_request(
                "POST",
                "/upload-csv",
                data={"dataset_type": dataset_type},
                files=multipart_files,
            )
            st.success(f"Uploaded {len(response.json())} file(s) as {dataset_label}.")
        except RuntimeError as exc:
            st.error(exc)


if analyze_clicked:
    if not selected_model:
        st.warning("Choose a Gemini model or enter a custom model code.")
        st.stop()

    with st.spinner("Running rules and generating the SEO document..."):
        try:
            payload = {"model": selected_model}
            if gemini_api_key.strip():
                payload["api_key"] = gemini_api_key.strip()
            response = api_request("POST", "/analyze", json=payload)
            st.session_state["tasks"] = response.json()
            st.success(f"Generated {len(st.session_state['tasks'])} SEO task(s).")
        except RuntimeError as exc:
            st.error(exc)


if reset_clicked:
    try:
        api_request("DELETE", "/reset")
        st.session_state["tasks"] = []
        st.success("Session reset.")
    except RuntimeError as exc:
        st.error(exc)


if "tasks" not in st.session_state:
    try:
        st.session_state["tasks"] = api_request("GET", "/results").json()
    except Exception:
        st.session_state["tasks"] = []


tasks = st.session_state["tasks"]
issue_types = sorted({task["issue"] for task in tasks})
selected_issues = st.multiselect("Issue filter", issue_types, default=issue_types)
filtered_tasks = [task for task in tasks if not selected_issues or task["issue"] in selected_issues]

issue_counts = Counter(task["issue"] for task in filtered_tasks)
avg_priority = average([float(task["priority_score"]) for task in filtered_tasks])
avg_confidence = average([float(task["confidence_score"]) for task in filtered_tasks])
high_priority = sum(1 for task in filtered_tasks if task["priority_score"] >= 80)

st.markdown(
    f"""
    <div class="dashboard-hero">
      <div>
        <h1 class="dashboard-title">AI SEO Copilot</h1>
        <div class="dashboard-subtitle">Unified Ahrefs issue intelligence, task priority, and action document</div>
      </div>
      <div class="status-pill">Backend: {API_BASE_URL}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Tasks</div>
        <div class="kpi-value">{len(filtered_tasks)}</div>
        <div class="kpi-foot">Current filtered workload</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Issue Types</div>
        <div class="kpi-value">{len(issue_counts)}</div>
        <div class="kpi-foot">Detected by deterministic rules</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Priority</div>
        <div class="kpi-value">{avg_priority}</div>
        <div class="kpi-foot">{high_priority} high-priority tasks</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Confidence</div>
        <div class="kpi-value">{avg_confidence}</div>
        <div class="kpi-foot">Evidence-backed confidence</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_tab, report_tab, tasks_tab = st.tabs(["Overview", "Action Document", "Task Data"])

with overview_tab:
    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section-title">Issue Distribution</div>', unsafe_allow_html=True)
        if issue_counts:
            issue_df = pd.DataFrame(
                {"Issue": list(issue_counts.keys()), "Count": list(issue_counts.values())}
            ).sort_values("Count", ascending=False)
            st.bar_chart(issue_df, x="Issue", y="Count", height=320)
        else:
            st.info("Upload Ahrefs exports and run analysis.")

    with right:
        st.markdown('<div class="section-title">Top Priority Problems</div>', unsafe_allow_html=True)
        if filtered_tasks:
            top_df = task_frame(
                sorted(filtered_tasks, key=lambda task: task["priority_score"], reverse=True)[:12]
            )
            st.dataframe(top_df, use_container_width=True, hide_index=True)
        else:
            st.info("No analyzed data yet.")

with report_tab:
    if not filtered_tasks:
        st.info("Run analysis to generate the consolidated SEO document.")
    else:
        try:
            preview_response = api_request("GET", "/report-preview")
            report_response = api_request("GET", "/report")
            report_text = preview_response.text
            preview_text = report_text.split("## All Problems And Tasks")[0].strip()
            col_a, col_b = st.columns([1, 3])
            with col_a:
                st.download_button(
                    "Download SEO PDF",
                    data=report_response.content,
                    file_name="seo_copilot_report.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            with col_b:
                st.caption("The PDF includes the summarized report plus the full task detail.")
            st.markdown(preview_text)
        except RuntimeError as exc:
            st.error(exc)

with tasks_tab:
    if not filtered_tasks:
        st.info("No task data available.")
    else:
        export_col, _ = st.columns([1, 3])
        with export_col:
            try:
                export_response = api_request("GET", f"/export?format={export_format}")
                st.download_button(
                    "Export task data",
                    data=export_response.content,
                    file_name=f"seo_tasks.{export_format}",
                    mime="application/json" if export_format == "json" else "text/csv",
                    use_container_width=True,
                )
            except RuntimeError:
                st.download_button(
                    "Export task data",
                    data=b"",
                    file_name=f"seo_tasks.{export_format}",
                    disabled=True,
                    use_container_width=True,
                )

        st.dataframe(task_frame(filtered_tasks), use_container_width=True, hide_index=True)
        show_cards = st.checkbox("Show task cards", value=False)
        if show_cards:
            for task in filtered_tasks[:100]:
                with st.expander(f"{task['issue']} - {task['page']}", expanded=False):
                    left, right = st.columns([1, 1])
                    with left:
                        st.subheader("Evidence")
                        st.write(task["evidence"])
                        st.subheader("AI explanation")
                        st.write(task["ai_explanation"])
                        st.subheader("Actions")
                        for action in task["actions"]:
                            st.write(f"- {action}")

                    with right:
                        generated = task.get("generated_content", {})
                        st.subheader("Generated SEO content")
                        for label, key in [
                            ("Titles", "titles"),
                            ("Meta descriptions", "meta_descriptions"),
                            ("Headings", "headings"),
                            ("FAQs", "faqs"),
                        ]:
                            values = generated.get(key, [])
                            st.markdown(f"**{label}**")
                            if values:
                                for value in values:
                                    st.write(f"- {value}")
                            else:
                                st.caption("insufficient data")
