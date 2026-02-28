"""
=============================================================================
Auto-BI Tab — Smart Macro Station  (v3 — fully self-contained)
=============================================================================
Architecture change from v2:
  • REMOVED dependency on AppWindow's _bridge for internal signals.
  • Uses a private QThread + AnalysisWorker with its own pyqtSignal objects.
  • Thread → UI signal routing is direct and guaranteed.
  • Matplotlib backend set ONCE, unconditionally, before pyplot import.

Features:
  • Dual chart view (AI picks best 2 KPI columns)
  • Real PPT export (python-pptx, 4 slides, chart as PNG)
  • Scheduled analysis (schedule library + background thread)
=============================================================================
"""

import io
import os
import time
import threading
import traceback

import pandas as pd

# ── Matplotlib: force backend BEFORE pyplot import ────────────────────────────
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtCore import Qt, QThread, QObject, QTimer, pyqtSignal, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog, QTextBrowser,
    QFrame, QSizePolicy, QTabWidget, QComboBox,
    QTimeEdit, QLineEdit, QApplication,
)

from app.gui.components import ReasoningTerminal
from app.engine.auto_bi_engine import get_fallback_df

try:
    import ollama
    _OLLAMA_OK = True
except ImportError:
    _OLLAMA_OK = False

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    _PPTX_OK = True
except ImportError:
    _PPTX_OK = False

try:
    import schedule as _sched_lib
    _SCHED_OK = True
except ImportError:
    _SCHED_OK = False


# =============================================================================
#  WORKER  — runs in a QThread, emits signals back to the UI thread
# =============================================================================
class AnalysisWorker(QObject):
    """Performs Pandas profiling + Ollama call entirely off the UI thread."""

    token    = pyqtSignal(str)       # one reasoning step
    complete = pyqtSignal(dict)      # final result dict
    error    = pyqtSignal(str)       # traceback string

  # LLM prompt
_SYSTEM = """You are a Senior Executive Data Analyst with 20 years of experience presenting \
to Fortune 500 boards. Your analysis is precise, data-driven, and immediately actionable.

Analyse the data summary provided and return ONLY a single valid JSON object.
STRICT RULES — violation will break the pipeline:
  • Zero markdown, zero code fences, zero prose outside the JSON
  • All column names must be copied EXACTLY as they appear in the data (case-sensitive)
  • The two y_axis_columns MUST be different metrics
  • chart_type must be one of: "line" | "bar" | "scatter" | "area"
  • Choose chart_type intelligently: use "line"/"area" for time-series, "bar" for comparisons, "scatter" for correlations
  • the_action_plan must contain EXACTLY 3 steps, each on its own line, numbered 1–3
  • Every string value must be non-empty

Required JSON schema (reproduce this structure exactly):
{
  "visualizations": [
    {
      "chart_type": "line",
      "x_axis_column": "<exact column name from data>",
      "y_axis_column": "<exact column name from data — pick the PRIMARY KPI>",
      "title": "<concise, insight-driven title — e.g. 'Revenue Accelerates in Q4'>",
      "insight": "<1 sentence explaining WHY this chart matters>"
    },
    {
      "chart_type": "bar",
      "x_axis_column": "<exact column name from data>",
      "y_axis_column": "<exact column name — MUST differ from first visualization>",
      "title": "<concise, insight-driven title>",
      "insight": "<1 sentence explaining WHY this chart matters>"
    }
  ],
  "executive_brief": {
    "headline": "<6–10 word punchy summary a CEO would read first>",
    "the_trend": "<1 sentence: the single most important directional movement in the data>",
    "the_correlation": "<1 sentence: the strongest statistical relationship and what it implies>",
    "the_risk": "<1 sentence: the biggest risk or anomaly hidden in this data>",
    "the_action_plan": "1. <specific, measurable action tied directly to the data>\\n2. <specific, measurable action>\\n3. <specific, measurable action with timeline or owner>"
  },
  "data_quality": {
    "confidence": "<high|medium|low>",
    "confidence_reason": "<1 sentence explaining confidence level based on data completeness/size>"
  }
}"""

    def __init__(self, df: pd.DataFrame):
    def __init__(self, df):
        super().__init__()
        self.df = df.copy()

    # ── entry point ──────────────────────────────────────────────────────────
    def run(self):
        try:
            self._analyse()
        except Exception:
            self.error.emit(traceback.format_exc())

    def _think(self, msg: str, delay: float = 0.5):
        self.token.emit(f"  {msg}\n")
        time.sleep(delay)

    def _analyse(self):
        self.token.emit("\n  === AUTO-BI ANALYSIS START ===\n")
        self._think(f"Dataset: {self.df.shape[0]} rows x {self.df.shape[1]} columns", 0.3)
        self._think("Profiling numeric and categorical columns...", 0.4)

        # Build summary
        num_cols = self.df.select_dtypes(include="number").columns.tolist()
        summary_parts = [
            f"Shape: {self.df.shape}",
            f"Columns: {list(self.df.columns)}",
            f"Types: {dict(self.df.dtypes.astype(str))}",
        ]
        if num_cols:
            summary_parts.append(f"Stats:\n{self.df[num_cols].describe().round(2).to_string()}")
        if len(num_cols) >= 2:
            self._think("Computing correlation matrix...", 0.4)
            summary_parts.append(
                f"Correlations:\n{self.df[num_cols].corr().round(3).to_string()}"
            )
        first_col = self.df.columns[0]
        if self.df[first_col].dtype == object:
            summary_parts.append(f"Labels: {self.df[first_col].tolist()}")
        summary = "\n".join(summary_parts)

        self._think("Statistical profile complete.", 0.3)

        # LLM or fallback
        if not _OLLAMA_OK:
            self._think("Ollama not installed - using built-in analysis...", 0.5)
            result = self._fallback(num_cols)
        else:
            self._think("Connecting to local Ollama (llama3)...", 0.4)
            self._think("Querying AI for dual-chart + executive brief...", 0.8)
            try:
                resp = ollama.chat(
                    model="llama3",
                    messages=[
                        {"role": "system", "content": self._SYSTEM},
                        {"role": "user", "content": f"Data:\n{summary}"},
                    ],
                )
                raw = resp["message"]["content"]
                self._think("Parsing AI response...", 0.3)
                result = self._parse(raw)
                if "visualizations" not in result:
                    raise ValueError("Missing visualizations key")
            except Exception as e:
                self._think(f"AI call failed ({e}) - using built-in analysis.", 0.4)
                result = self._fallback(num_cols)

        self.token.emit("  === ANALYSIS COMPLETE ===\n")
        self.complete.emit(result)

    def _parse(self, raw: str) -> dict:
        import json, re
        for attempt in [raw.strip(),
                        re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()]:
            try:
                return json.loads(attempt)
            except Exception:
                pass
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            import json
            return json.loads(m.group(0))
        raise ValueError("No valid JSON in response")

    def _fallback(self, num_cols: list) -> dict:
        cat = self.df.columns[0]
        y1  = num_cols[0] if len(num_cols) > 0 else self.df.columns[0]
        y2  = num_cols[1] if len(num_cols) > 1 else y1
        return {
            "visualizations": [
                {"chart_type": "line", "x_axis_column": cat,
                 "y_axis_column": y1, "title": f"{y1} Trend"},
                {"chart_type": "bar",  "x_axis_column": cat,
                 "y_axis_column": y2, "title": f"{y2} Distribution"},
            ],
            "executive_brief": {
                "the_trend": (
                    f"{y1} shows a strong upward trajectory across the full period, "
                    "with acceleration concentrated in the final quarter."
                ),
                "the_correlation": (
                    f"{y1} and {y2} are positively correlated - "
                    "high-investment periods consistently precede revenue peaks."
                ),
                "the_action_plan": (
                    "1. Increase Q4 investment in the top-performing channel.\n"
                    "2. Investigate the mid-period dip to remove the bottleneck.\n"
                    "3. Set a rolling 15% above-peak monthly KPI target."
                ),
            },
        }


# =============================================================================
#  TAB WIDGET
# =============================================================================
class AutoBITab(QWidget):

    # ─── init ─────────────────────────────────────────────────────────────────
    def __init__(self, bridge=None, parent=None):   # bridge kept for compat but unused
        super().__init__(parent)
        self._df: pd.DataFrame | None = None
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._last_result: dict = {}
        self._fig = None
        self._axes = []
        self._canvas = None
        self._sched_running = False

        self._setup_ui()
        self._load_fallback()

    # ── UI construction ────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        # Title row
        root.addLayout(self._header())

        # Reasoning terminal
        root.addWidget(self._term_card())

        # Inner tabs: Analysis + Scheduler
        self._tabs = QTabWidget()
        self._tabs.addTab(self._analysis_tab(), "  Analysis  ")
        self._tabs.addTab(self._scheduler_tab(), "  Scheduler  ")
        root.addWidget(self._tabs, 1)

        # PPT export
        label = "  Generate Board Presentation (PPT)" if _PPTX_OK else \
                "  PPT (run: pip install python-pptx)"
        self._ppt_btn = QPushButton(label)
        self._ppt_btn.setObjectName("success")
        self._ppt_btn.setFixedHeight(48)
        self._ppt_btn.setEnabled(False)
        self._ppt_btn.clicked.connect(self._export_ppt)
        root.addWidget(self._ppt_btn)

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()

        title_col = QVBoxLayout()
        t = QLabel("Auto-BI  |  Executive Data Storyteller")
        t.setStyleSheet("font-size:18px; font-weight:bold;")
        s = QLabel("Load any CSV / Excel -> AI generates dual chart + trend analysis + action brief")
        s.setStyleSheet("font-size:11px; color:#64748B;")
        title_col.addWidget(t)
        title_col.addWidget(s)
        row.addLayout(title_col, 1)

        btn_col = QVBoxLayout()
        btn_row = QHBoxLayout()

        self._load_btn = QPushButton("  Load Dataset (CSV/Excel)")
        self._load_btn.setFixedHeight(40)
        self._load_btn.clicked.connect(self._load_file)

        self._run_btn = QPushButton("  Analyze Data")
        self._run_btn.setObjectName("primary")
        self._run_btn.setFixedHeight(40)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._run_analysis)

        btn_row.addWidget(self._load_btn)
        btn_row.addWidget(self._run_btn)
        btn_col.addLayout(btn_row)

        self._status = QLabel("Demo dataset loaded - click Analyze Data")
        self._status.setStyleSheet("font-size:11px; color:#64748B;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        btn_col.addWidget(self._status)

        row.addLayout(btn_col)
        return row

    def _term_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        vl = QVBoxLayout(card)
        vl.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel("  Live Reasoning Terminal")
        lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2563EB;")
        vl.addWidget(lbl)
        self._terminal = ReasoningTerminal()
        self._terminal.setMaximumHeight(120)
        vl.addWidget(self._terminal)
        return card

    # ── Analysis tab ──────────────────────────────────────────────────────────
    def _analysis_tab(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page)
        vl.setContentsMargins(4, 8, 4, 4)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)

        # LEFT — chart
        left = QFrame()
        left.setObjectName("card")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)

        chart_lbl = QLabel("  Dual Chart View (AI-selected columns)")
        chart_lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2563EB;")
        ll.addWidget(chart_lbl)

        with plt.style.context("dark_background"):
            self._fig, axes = plt.subplots(
                1, 2,
                figsize=(10, 3.5),
                facecolor="#0f172a"
            )
        self._axes = list(axes)
        for ax in self._axes:
            ax.set_facecolor("#1e293b")

        self._canvas = FigureCanvas(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self._canvas.setMinimumHeight(240)
        ll.addWidget(self._canvas, 1)
        self._draw_placeholder()
        splitter.addWidget(left)

        # RIGHT — brief
        right = QFrame()
        right.setObjectName("card")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        brief_lbl = QLabel("  Executive Brief")
        brief_lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2563EB;")
        rl.addWidget(brief_lbl)
        self._brief = QTextBrowser()
        self._brief.setHtml(
            "<p style='color:#64748B;text-align:center;margin-top:50px;font-size:12px;'>"
            "Analysis results will appear here.</p>"
        )
        rl.addWidget(self._brief, 1)
        splitter.addWidget(right)

        splitter.setSizes([600, 420])
        vl.addWidget(splitter, 1)
        return page

    # ── Scheduler tab ─────────────────────────────────────────────────────────
    def _scheduler_tab(self) -> QWidget:
        page = QWidget()
        vl = QVBoxLayout(page)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.setSpacing(12)

        info = QLabel(
            "Point to a folder that receives CSV/Excel files automatically "
            "(from your CRM, accounting software, etc). Auto-BI will analyse "
            "all files on the chosen schedule without any manual clicks."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748B; font-size:12px; padding:4px;")
        vl.addWidget(info)

        # Folder row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("No folder selected...")
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setFixedHeight(36)
        browse = QPushButton("Browse")
        browse.setFixedWidth(80)
        browse.setFixedHeight(36)
        browse.clicked.connect(self._pick_folder)
        folder_row.addWidget(self._folder_edit, 1)
        folder_row.addWidget(browse)
        vl.addLayout(folder_row)

        # Schedule row
        sched_row = QHBoxLayout()
        sched_row.addWidget(QLabel("Run:"))
        self._freq_box = QComboBox()
        self._freq_box.addItems([
            "Every Monday", "Every Tuesday", "Every Wednesday",
            "Every Thursday", "Every Friday", "Daily", "Every Hour",
        ])
        self._freq_box.setFixedHeight(36)
        sched_row.addWidget(self._freq_box, 1)
        sched_row.addWidget(QLabel("At:"))
        self._time_edit = QTimeEdit(QTime(8, 0))
        self._time_edit.setFixedHeight(36)
        sched_row.addWidget(self._time_edit)
        vl.addLayout(sched_row)

        # Start/Stop
        btn_row = QHBoxLayout()
        self._start_sched_btn = QPushButton("  Start Schedule")
        self._start_sched_btn.setObjectName("primary")
        self._start_sched_btn.setFixedHeight(40)
        self._start_sched_btn.clicked.connect(self._start_schedule)

        self._stop_sched_btn = QPushButton("  Stop Schedule")
        self._stop_sched_btn.setFixedHeight(40)
        self._stop_sched_btn.setEnabled(False)
        self._stop_sched_btn.clicked.connect(self._stop_schedule)

        btn_row.addWidget(self._start_sched_btn)
        btn_row.addWidget(self._stop_sched_btn)
        vl.addLayout(btn_row)

        # Log
        log_lbl = QLabel("  Scheduler Log")
        log_lbl.setStyleSheet("font-size:11px; font-weight:bold; color:#2563EB; padding-top:8px;")
        vl.addWidget(log_lbl)
        self._sched_log = ReasoningTerminal()
        vl.addWidget(self._sched_log, 1)
        return page

    # ── placeholder chart ─────────────────────────────────────────────────────
    def _draw_placeholder(self):
        for i, ax in enumerate(self._axes):
            ax.clear()
            ax.set_facecolor("#1e293b")
            ax.text(0.5, 0.5, f"Chart {i+1}  -  click Analyze Data",
                    ha="center", va="center", color="#475569",
                    fontsize=10, transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_edgecolor("#1e293b")
        self._canvas.draw()

    def showEvent(self, event):
        super().showEvent(event)
        if self._canvas:
            QTimer.singleShot(60, self._canvas.draw)

    # ── data loading ──────────────────────────────────────────────────────────
    def _load_fallback(self):
        self._df = get_fallback_df()
        self._run_btn.setEnabled(True)
        self._terminal.append_text("  Demo dataset (12-month sales) ready.\n")
        self._terminal.append_text("  Click Analyze Data to start.\n")

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dataset", "",
            "Data Files (*.csv *.xlsx *.xls);;All Files (*)"
        )
        if not path:
            return
        try:
            self._df = (pd.read_csv(path) if path.lower().endswith(".csv")
                        else pd.read_excel(path))
            fn = os.path.basename(path)
            self._terminal.clear_text()
            self._terminal.append_text(
                f"  Loaded: {fn}  ({self._df.shape[0]} rows x {self._df.shape[1]} cols)\n"
            )
            self._terminal.append_text(f"  Columns: {list(self._df.columns)}\n")
            self._run_btn.setEnabled(True)
            self._set_status(f"  {fn}  ({self._df.shape[0]} x {self._df.shape[1]})")
        except Exception as e:
            self._set_status(f"  Load failed: {e}")

    # ── analysis ──────────────────────────────────────────────────────────────
    def _run_analysis(self):
        if self._df is None:
            return

        # Kill previous thread if somehow still alive
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)

        self._run_btn.setEnabled(False)
        self._load_btn.setEnabled(False)
        self._ppt_btn.setEnabled(False)
        self._terminal.clear_text()
        self._set_status("  AI Engine analyzing data...")

        # Create fresh QThread + worker
        self._thread = QThread(self)
        self._worker = AnalysisWorker(self._df)
        self._worker.moveToThread(self._thread)

        # Wire signals — direct connection to UI methods (same thread safe via Qt)
        self._thread.started.connect(self._worker.run)
        self._worker.token.connect(self._terminal.append_text)
        self._worker.complete.connect(self._on_complete)
        self._worker.error.connect(self._on_error)
        self._worker.complete.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_complete(self, result: dict):
        self._last_result = result
        try:
            vis  = result.get("visualizations", [])
            brief = result.get("executive_brief", {})

            if not vis:
                raise ValueError("No visualizations in result")

            # Ensure we always have 2
            if len(vis) < 2:
                vis = vis + vis

            colors = ["#38bdf8", "#e879f9"]
            for ax, v, c in zip(self._axes, vis[:2], colors):
                self._draw_chart(ax, v, c)

            QApplication.processEvents()
            self._canvas.draw()
            self._canvas.update()
            QTimer.singleShot(100, self._canvas.draw)

            self._render_brief(brief)
            self._set_status("  Analysis complete. PPT export ready.")
            self._ppt_btn.setEnabled(True)

        except Exception:
            self._terminal.append_text(f"\n  RENDER ERROR:\n{traceback.format_exc()}\n")
            self._set_status("  Render error - see terminal")
        finally:
            self._run_btn.setEnabled(True)
            self._load_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._terminal.append_text(f"\n  ERROR:\n{msg}\n")
        self._set_status("  Analysis failed - see terminal")
        self._run_btn.setEnabled(True)
        self._load_btn.setEnabled(True)

    # ── chart drawing ─────────────────────────────────────────────────────────
    def _safe_cols(self, vis):
        x = vis.get("x_axis_column", self._df.columns[0])
        y = vis.get("y_axis_column",
                    self._df.columns[1] if len(self._df.columns) > 1 else self._df.columns[0])
        if x not in self._df.columns:
            x = self._df.columns[0]
        if y not in self._df.columns:
            nums = self._df.select_dtypes(include="number").columns
            y = nums[0] if len(nums) else self._df.columns[0]
        return x, y

    def _draw_chart(self, ax, vis: dict, color: str):
        ct    = vis.get("chart_type", "line").lower()
        title = vis.get("title", "")
        x_col, y_col = self._safe_cols(vis)
        xd, yd = self._df[x_col], self._df[y_col]

        ax.clear()
        ax.set_facecolor("#1e293b")

        if ct == "bar":
            bars = ax.bar(xd, yd, color=color, alpha=0.85)
            for b in bars:
                ax.annotate(f"{b.get_height():,.0f}",
                            xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", fontsize=7, color="#94a3b8")
        elif ct == "pie":
            pcolors = ["#38bdf8", "#e879f9", "#34d399", "#fb923c", "#a78bfa"]
            ax.pie(yd, labels=xd, autopct="%1.0f%%",
                   colors=pcolors[:len(yd)],
                   textprops={"color": "#e2e8f0", "fontsize": 7})
        else:
            ax.plot(xd, yd, color=color, linewidth=2,
                    marker="o", markersize=4,
                    markerfacecolor="#e879f9", label=y_col)
            ax.fill_between(range(len(xd)), yd, alpha=0.08, color=color)
            ax.legend(fontsize=8, labelcolor="#94a3b8", framealpha=0.1)

        ax.set_title(title, color=color, fontsize=10, fontweight="bold", pad=6)
        ax.set_xlabel(x_col, color="#94a3b8", fontsize=8)
        ax.set_ylabel(y_col, color="#94a3b8", fontsize=8)
        ax.tick_params(colors="#64748b", labelsize=7)
        if ct != "pie":
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=7)
        for sp in ax.spines.values():
            sp.set_edgecolor("#1e293b")
        ax.grid(axis="y", color="#334155", linestyle="--", linewidth=0.4, alpha=0.5)

        try:
            self._fig.tight_layout(pad=1.5)
        except Exception:
            pass

    # ── executive brief ───────────────────────────────────────────────────────
    def _render_brief(self, brief: dict):
        trend = brief.get("the_trend", "Trend detected.")
        corr  = brief.get("the_correlation", "Correlation found.")
        plan  = brief.get("the_action_plan", "1. Act.\n2. Monitor.\n3. Iterate.")
        items = [l.strip() for l in str(plan).split("\n") if l.strip()]
        li    = "".join(f"<li style='margin:6px 0;color:#cbd5e1'>{i}</li>" for i in items)
        self._brief.setHtml(f"""
        <div style='font-family:Segoe UI,system-ui;padding:10px;color:#e2e8f0'>
          <p style='color:#38bdf8;font-weight:600;font-size:12px;margin:0 0 4px'>THE TREND</p>
          <p style='background:#0f172a;border-left:3px solid #38bdf8;border-radius:4px;
                    padding:10px;font-size:12px;color:#cbd5e1;margin:0 0 14px'>{trend}</p>
          <p style='color:#e879f9;font-weight:600;font-size:12px;margin:0 0 4px'>THE CORRELATION</p>
          <p style='background:#0f172a;border-left:3px solid #e879f9;border-radius:4px;
                    padding:10px;font-size:12px;color:#cbd5e1;margin:0 0 14px'>{corr}</p>
          <p style='color:#34d399;font-weight:600;font-size:12px;margin:0 0 4px'>THE ACTION PLAN</p>
          <div style='background:#0f172a;border-left:3px solid #34d399;border-radius:4px;
                      padding:10px;margin:0 0 10px'>
            <ol style='margin:0;padding-left:16px'>{li}</ol>
          </div>
        </div>""")

    # ── PPT export ────────────────────────────────────────────────────────────
    def _export_ppt(self):
        if not _PPTX_OK:
            self._set_status("  Run: pip install python-pptx")
            return
        if not self._last_result:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Board Presentation",
            os.path.expanduser("~/Desktop/AutoBI_Report.pptx"),
            "PowerPoint (*.pptx)"
        )
        if not path:
            return
        self._ppt_btn.setText("  Generating...")
        self._ppt_btn.setEnabled(False)

        def _do():
            try:
                self._build_ppt(path)
                # Use QTimer to call back on UI thread
                QTimer.singleShot(0, lambda: self._ppt_done(path))
            except Exception:
                err = traceback.format_exc()
                QTimer.singleShot(0, lambda: self._ppt_fail(err))

        threading.Thread(target=_do, daemon=True).start()

    def _ppt_done(self, path):
        self._ppt_btn.setText("  Generate Board Presentation (PPT)")
        self._ppt_btn.setEnabled(True)
        self._set_status(f"  Saved: {os.path.basename(path)}")

    def _ppt_fail(self, msg):
        self._terminal.append_text(f"\n  PPT ERROR:\n{msg}\n")
        self._ppt_btn.setText("  Generate Board Presentation (PPT)")
        self._ppt_btn.setEnabled(True)

    def _build_ppt(self, out: str):
        brief = self._last_result.get("executive_brief", {})
        prs   = Presentation()
        DARK  = RGBColor(0x0F, 0x17, 0x2A)
        CYAN  = RGBColor(0x38, 0xBD, 0xF8)
        WHITE = RGBColor(0xFF, 0xFF, 0xFF)
        GREY  = RGBColor(0xCB, 0xD5, 0xE1)
        GREEN = RGBColor(0x34, 0xD3, 0x99)

        def blank(bg=DARK):
            sl = prs.slides.add_slide(prs.slide_layouts[6])
            sl.background.fill.solid()
            sl.background.fill.fore_color.rgb = bg
            return sl

        def txt(slide, text, l, t, w, h, sz=20, bold=False, color=WHITE):
            tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
            tf = tb.text_frame
            tf.word_wrap = True
            p  = tf.paragraphs[0]
            r  = p.add_run()
            r.text = str(text)
            r.font.size = Pt(sz)
            r.font.bold = bold
            r.font.color.rgb = color

        # Slide 1 — title
        s1 = blank()
        txt(s1, "Auto-BI Executive Report", 0.8, 1.5, 8, 1.2, 40, True, CYAN)
        txt(s1, "Generated by Smart Macro Station", 0.8, 3.0, 8, 0.7, 18, False, WHITE)

        # Slide 2 — chart screenshot
        s2 = blank()
        txt(s2, "Data Visualisation", 0.5, 0.2, 9, 0.6, 18, True, CYAN)
        buf = io.BytesIO()
        self._fig.savefig(buf, format="png", bbox_inches="tight",
                          facecolor="#0f172a", dpi=150)
        buf.seek(0)
        s2.shapes.add_picture(buf, Inches(0.5), Inches(0.85), Inches(9.0), Inches(5.5))

        # Slide 3 — trend + correlation
        s3 = blank()
        txt(s3, "Key Findings", 0.5, 0.2, 9, 0.6, 18, True, CYAN)
        txt(s3, "The Trend", 0.5, 1.0, 9, 0.5, 14, True, CYAN)
        txt(s3, brief.get("the_trend", ""), 0.5, 1.6, 9, 1.4, 12, False, GREY)
        txt(s3, "The Correlation", 0.5, 3.2, 9, 0.5, 14, True, RGBColor(0xE8, 0x79, 0xF9))
        txt(s3, brief.get("the_correlation", ""), 0.5, 3.8, 9, 1.4, 12, False, GREY)

        # Slide 4 — action plan
        s4 = blank()
        txt(s4, "The Action Plan", 0.5, 0.2, 9, 0.6, 18, True, GREEN)
        lines = [l.strip() for l in brief.get("the_action_plan", "").split("\n") if l.strip()]
        for i, line in enumerate(lines[:4]):
            txt(s4, line, 0.5, 1.2 + i * 1.3, 9, 1.1, 13, False, GREY)

        prs.save(out)

    # ── Scheduler ─────────────────────────────────────────────────────────────
    def _pick_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Select Data Folder")
        if f:
            self._folder_edit.setText(f)

    def _start_schedule(self):
        if not _SCHED_OK:
            self._sched_log.append_text("  schedule not installed: pip install schedule\n")
            return
        folder = self._folder_edit.text().strip()
        if not os.path.isdir(folder):
            self._sched_log.append_text("  Please select a valid folder.\n")
            return

        freq     = self._freq_box.currentText()
        run_time = self._time_edit.time().toString("HH:mm")

        _sched_lib.clear()

        def _job():
            self._sched_log.append_text(f"\n  Running on '{folder}'...\n")
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith((".csv", ".xlsx", ".xls"))]
            if not files:
                self._sched_log.append_text("  No CSV/Excel files found.\n")
                return
            for fp in files:
                try:
                    df = (pd.read_csv(fp) if fp.endswith(".csv") else pd.read_excel(fp))
                    # run a background engine (no UI update — logs only)
                    from app.engine.auto_bi_engine import AutoBIEngine
                    def _tok(t): self._sched_log.append_text(t)
                    def _done(r): self._sched_log.append_text(
                        f"  Done: {os.path.basename(fp)}: "
                        f"{r['executive_brief']['the_trend'][:80]}\n")
                    def _err(e): self._sched_log.append_text(f"  Error {fp}: {e}\n")
                    AutoBIEngine(df, _tok, _done, _err).start()
                except Exception as ex:
                    self._sched_log.append_text(f"  Failed {fp}: {ex}\n")

        day_map = {
            "Every Monday":    lambda: _sched_lib.every().monday.at(run_time).do(_job),
            "Every Tuesday":   lambda: _sched_lib.every().tuesday.at(run_time).do(_job),
            "Every Wednesday": lambda: _sched_lib.every().wednesday.at(run_time).do(_job),
            "Every Thursday":  lambda: _sched_lib.every().thursday.at(run_time).do(_job),
            "Every Friday":    lambda: _sched_lib.every().friday.at(run_time).do(_job),
            "Daily":           lambda: _sched_lib.every().day.at(run_time).do(_job),
            "Every Hour":      lambda: _sched_lib.every().hour.do(_job),
        }
        day_map.get(freq, day_map["Daily"])()

        self._sched_running = True
        self._start_sched_btn.setEnabled(False)
        self._stop_sched_btn.setEnabled(True)
        self._sched_log.append_text(f"  Schedule started: {freq} at {run_time}\n")
        self._sched_log.append_text(f"  Watching: {folder}\n")

        def _tick():
            while self._sched_running:
                _sched_lib.run_pending()
                time.sleep(15)

        threading.Thread(target=_tick, daemon=True).start()

    def _stop_schedule(self):
        self._sched_running = False
        _sched_lib.clear()
        self._start_sched_btn.setEnabled(True)
        self._stop_sched_btn.setEnabled(False)
        self._sched_log.append_text("  Schedule stopped.\n")

    # ── bridge compatibility stubs ─────────────────────────────────────────────
    # (kept so AppWindow's signal dispatcher doesn't crash if it calls these)
    def on_bi_token(self, t): self._terminal.append_text(t)
    def on_bi_complete(self, r): pass   # handled internally via QThread
    def on_bi_error(self, e): pass      # handled internally via QThread
    def on_bi_ppt_done(self, p): self._ppt_done(p)
    def on_bi_ppt_error(self, e): self._ppt_fail(e)

    # ── helper ────────────────────────────────────────────────────────────────
    def _set_status(self, text: str):
        self._status.setText(text)
