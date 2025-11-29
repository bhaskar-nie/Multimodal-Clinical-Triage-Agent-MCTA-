import base64
import io
import json
from typing import Any, Dict, List

import matplotlib.pyplot as plt


def generate_vitals_visualization(time_series_data: str) -> str:
    """
    Executes Python code to plot time-series vitals (SpO2, HR)
    for graphical analysis and returns the resulting PNG as a Base64 string.

    The time_series_data argument is expected to be a JSON string encoding a list
    of objects with at least:
      - "time": str
      - "SpO2": float or int (capital S)
      - "HeartRate": int (capital H)
    """
    # 1. Parse data (JSON string from agent request)
    data: List[Dict[str, Any]] = json.loads(time_series_data)

    if not data:
        raise ValueError("time_series_data must contain at least one data point.")

    # 2. Extract components
    times = [d["time"] for d in data]
    spo2 = [d["SpO2"] for d in data]
    hr = [d["HeartRate"] for d in data]

    # 3. Plot using Matplotlib (make it look professional)
    fig, ax1 = plt.subplots(figsize=(8, 4))
    
    # SpO2 on primary axis
    ax1.plot(times, spo2, label="SpO2 (%)", color="teal", marker="o", linewidth=2)
    ax1.set_xlabel("Time (Hourly)")
    ax1.set_ylabel("SpO2 (%)", color="teal")
    ax1.tick_params(axis="y", labelcolor="teal")
    ax1.set_ylim(80, 100)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Heart Rate on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(
        times, hr, label="Heart Rate (bpm)", color="orange", marker="x", linestyle="--"
    )
    ax2.set_ylabel("Heart Rate (bpm)", color="orange")
    ax2.tick_params(axis="y", labelcolor="orange")

    plt.title("Critical Vitals Trend Confirmation", fontsize=10)
    fig.tight_layout()  # Adjust layout to prevent clipping

    # 4. Save plot to buffer and encode to Base64
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)  # Close figure to free memory
    base64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

    return base64_image


def calculate_sepsis_risk(
    heart_rate: int,
    blood_pressure: int,
    lactate_level: float,
    respiratory_rate: int,
) -> dict:
    """
    Simplified sepsis risk scoring function for hackathon demonstration.

    This is NOT a real clinical tool and must not be used for real patient care.
    """
    score = (heart_rate // 10) + (respiratory_rate // 5) + int(lactate_level * 3)

    category = "High Risk" if score >= 20 else "Low Risk"

    return {"risk_score": int(score), "score_category": category}


# Hour 5-6: Both tools enabled for autonomous agentic tool use
TOOL_CONFIG = [calculate_sepsis_risk, generate_vitals_visualization]



