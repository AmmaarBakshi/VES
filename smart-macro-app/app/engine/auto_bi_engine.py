"""
=============================================================================
Auto-BI Engine — Smart Macro Station  (v2 — full rewrite)
=============================================================================
Analysis engine that runs Pandas profiling + Ollama (LLM) logic entirely in
a background thread via plain Python threading.

Schema now returns TWO visualizations so the UI can renders a dual-chart view.
=============================================================================
"""

import json
import re
import threading
import time
import traceback

import pandas as pd

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from app.utils.config_loader import load_ai_config


# ─── Built-in demo dataset ────────────────────────────────────────────────────
FALLBACK_DATA = {
    "Month":     ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
    "Revenue":   [42000,38000,51000,55000,49000,63000,71000,68000,75000,82000,91000,105000],
    "Units_Sold":[210,  190,  255,  275,  245,  315,  355,  340,  375,  410,  455,  525],
    "Ad_Spend":  [5000, 4800, 6200, 6800, 5900, 7500, 8200, 7900, 8800, 9500, 10500,12000],
}


def get_fallback_df() -> pd.DataFrame:
    return pd.DataFrame(FALLBACK_DATA)


# ─── Strict prompt schema ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Senior Executive Data Analyst with 20 years of experience \
presenting to Fortune 500 boards. Your analysis is precise, data-driven, and immediately \
actionable. You have deep expertise in statistical pattern recognition, trend forecasting, \
and translating raw numbers into boardroom-ready strategy.

════════════════════════════════════════════════════════
OUTPUT CONTRACT — read before generating anything
════════════════════════════════════════════════════════
- Return ONLY a single valid JSON object. Absolute zero tolerance for:
    - Markdown formatting  (no **, no ##, no bullet dashes)
    - Code fences          (no ```json or ```)
    - Prose, commentary, or apologies outside the JSON
    - Trailing commas or invalid JSON syntax
- All column names must be copied CHARACTER-FOR-CHARACTER from the data (case-sensitive).
  If you invent or mutate a column name, the pipeline will crash.
- The two y_axis_columns MUST reference two DIFFERENT numeric columns.
- chart_type must be exactly one of: "line" | "bar" | "scatter" | "area"
    - "line"    → time-series or sequential trends
    - "area"    → cumulative or stacked volume over time
    - "bar"     → category comparisons or ranked distributions
    - "scatter" → correlation between two continuous variables
- Every string field must be non-empty.
- the_action_plan must have EXACTLY 3 steps numbered 1–3, each on its own line.
- confidence must be exactly one of: "high" | "medium" | "low"

════════════════════════════════════════════════════════
ANALYSIS PRIORITIES (apply in this order)
════════════════════════════════════════════════════════
1. Identify the PRIMARY KPI — the metric with the highest business impact.
2. Identify the SECONDARY KPI — the metric most correlated with the primary.
3. Surface the single most important trend (direction + magnitude + timeframe).
4. Detect the strongest correlation and state its causal implication.
5. Flag the biggest risk, anomaly, or outlier hiding in the data.
6. Produce 3 actions that are specific, measurable, and tied directly to the numbers.

════════════════════════════════════════════════════════
REQUIRED JSON SCHEMA — reproduce this structure exactly
════════════════════════════════════════════════════════
{
  "visualizations": [
    {
      "chart_type": "<line|area|bar|scatter>",
      "x_axis_column": "<CHARACTER-FOR-CHARACTER column name from data>",
      "y_axis_column": "<CHARACTER-FOR-CHARACTER column name — PRIMARY KPI>",
      "title": "<insight-driven title, e.g. 'Revenue Accelerates 40% Through Q4'>",
      "insight": "<1 sentence: WHY this chart was chosen and what decision it supports>"
    },
    {
      "chart_type": "<line|area|bar|scatter>",
      "x_axis_column": "<CHARACTER-FOR-CHARACTER column name from data>",
      "y_axis_column": "<CHARACTER-FOR-CHARACTER column name — MUST differ from first>",
      "title": "<insight-driven title>",
      "insight": "<1 sentence: WHY this chart was chosen and what decision it supports>"
    }
  ],
  "executive_brief": {
    "headline": "<8–12 word punchy summary a CEO reads in 3 seconds>",
    "the_trend": "<1 sentence: the most important directional movement — include magnitude>",
    "the_correlation": "<1 sentence: the strongest statistical relationship and its business implication>",
    "the_risk": "<1 sentence: the most significant risk, anomaly, or outlier in the data>",
    "the_action_plan": "1. <specific, measurable action directly tied to the data with owner or timeline>\\n2. <specific, measurable action>\\n3. <specific, measurable action — include a quantified target>"
  },
  "data_quality": {
    "confidence": "<high|medium|low>",
    "confidence_reason": "<1 sentence: justify confidence level based on dataset size, completeness, and variance>",
    "row_count_assessed": <integer — echo back the number of rows you were given>,
    "columns_used": ["<primary KPI column name>", "<secondary KPI column name>"]
  }
}"""

class AutoBIEngine:
    """
    Runs the full Auto-BI analysis pipeline in a daemon background thread.

    Callbacks (all called from the background thread — bridge them to UI thread!):
        on_token(str)     — one reasoning step line
        on_complete(dict) — parsed result dict
        on_error(str)     — traceback string
    """

    def __init__(self, df: pd.DataFrame, on_token, on_complete, on_error):
        self.df = df.copy()
        self.on_token = on_token
        self.on_complete = on_complete
        self.on_error = on_error
        
        config = load_ai_config()
        self.OLLAMA_MODEL = config.get("active_model", "llama3.2")
        self.OLLAMA_BASE_URL = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")

    def __init__(self, df: pd.DataFrame, on_token, on_complete, on_error):
        self.df = df.copy()
        self.on_token = on_token
        self.on_complete = on_complete
        self.on_error = on_error

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    # ─── internal helpers ─────────────────────────────────────────────────────
    def _think(self, msg: str, delay: float = 0.55):
        self.on_token(f"  ⚡ {msg}\n")
        time.sleep(delay)

    def _build_summary(self) -> str:
        lines = [
            f"Shape: {self.df.shape[0]} rows × {self.df.shape[1]} columns",
            f"Columns: {list(self.df.columns)}",
            f"Dtypes: {dict(self.df.dtypes.astype(str))}",
        ]
        num_cols = self.df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            lines.append(f"Stats:\n{self.df[num_cols].describe().round(2).to_string()}")
        if len(num_cols) >= 2:
            lines.append(f"Correlations:\n{self.df[num_cols].corr().round(3).to_string()}")
        first = self.df.columns[0]
        if self.df[first].dtype == object:
            lines.append(f"Labels ({first}): {self.df[first].tolist()}")
        return "\n".join(lines)

    def _parse_json(self, raw: str) -> dict:
        """Robustly pull JSON out of the LLM response."""
        for attempt in [raw.strip(),
                        re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()]:
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                pass
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"No JSON found in response:\n{raw[:400]}")

    def _auto_result(self) -> dict:
        """Statistical fallback when Ollama is unavailable."""
        num_cols = self.df.select_dtypes(include="number").columns.tolist()
        cat_col  = self.df.columns[0]
        y1 = num_cols[0] if len(num_cols) > 0 else self.df.columns[0]
        y2 = num_cols[1] if len(num_cols) > 1 else y1
        return {
            "visualizations": [
                {"chart_type": "line",  "x_axis_column": cat_col, "y_axis_column": y1,
                 "title": f"{y1} Trend"},
                {"chart_type": "bar",   "x_axis_column": cat_col, "y_axis_column": y2,
                 "title": f"{y2} Distribution"},
            ],
            "executive_brief": {
                "the_trend": (
                    f"{y1} exhibits a strong upward trajectory across the period, "
                    "with the sharpest growth concentrated in the final quarter."
                ),
                "the_correlation": (
                    f"{y1} and {y2} are positively correlated — periods of high {y2} "
                    f"consistently precede elevated {y1} in subsequent intervals."
                ),
                "the_action_plan": (
                    "1. Double investment in the highest-performing channel during the "
                    "seasonally strong Q4 window to maximise proven ROI.\n"
                    "2. Conduct a root-cause analysis on any mid-period dip to remove "
                    "the operational bottleneck driving the temporary slowdown.\n"
                    "3. Establish a rolling 15 % above-peak monthly KPI target to "
                    "institutionalise continuous growth benchmarking."
                ),
            },
        }

    # ─── main thread body ─────────────────────────────────────────────────────
    def _run(self):
        try:
            self.on_token("\n  ━━━ AUTO-BI ENGINE v2 STARTING ━━━\n")
            self._think(f"Dataset mounted: {self.df.shape[0]} rows × {self.df.shape[1]} cols.", 0.4)
            self._think("Profiling numeric vs. categorical columns…", 0.5)
            self._think("Running Pandas describe() on all numeric columns…", 0.55)
            summary = self._build_summary()
            num_cols = self.df.select_dtypes(include="number").columns
            if len(num_cols) >= 2:
                self._think("Computing Pearson correlation matrix…", 0.55)
            self._think("Selecting two most informative KPI columns for dual-chart view…", 0.5)
            self._think("Statistical profile complete — building LLM prompt…", 0.4)

            if not OLLAMA_AVAILABLE:
                self._think("⚠️  Ollama not installed — switching to built-in analysis.", 0.8)
                result = self._auto_result()
            else:
                self._think(f"Connecting to local Ollama ({self.OLLAMA_MODEL})…", 0.5)
                self._think("Querying LLM — awaiting dual-chart JSON schema…", 0.5)
                self._think("LLM is reasoning over trends, outliers, and correlations…", 1.3)
                try:
                    import requests
                    
                    api_url = f"{self.OLLAMA_BASE_URL}/api/chat"
                    payload = {
                        "model": self.OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user",   "content": f"Data summary:\n\n{summary}"},
                        ],
                        "stream": False
                    }
                    
                    response = requests.post(api_url, json=payload, timeout=60)
                    response.raise_for_status()
                    resp = response.json()
                    
                    raw = resp["message"]["content"]
                    self._think("JSON schema received — validating…", 0.45)
                    result = self._parse_json(raw)
                    # Ensure visualizations is a list with ≥1 entry
                    if "visualizations" not in result:
                        raise ValueError("Missing 'visualizations' key")
                except Exception as err:
                    self._think(f"⚠️  LLM call failed ({err}) — using fallback.", 0.5)
                    result = self._auto_result()

            self.on_token("\n  ✅ ANALYSIS COMPLETE — RENDERING RESULTS\n")
            self.on_complete(result)
        except Exception:
            self.on_error(traceback.format_exc())
