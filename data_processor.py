from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class LabPanel:
    wbc: float  # x10^9/L
    lactate: float  # mmol/L
    creatinine: float  # mg/dL


@dataclass
class VitalPoint:
    time: str  # human-readable time label
    spo2: float
    heart_rate: int
    respiratory_rate: int


def summarize_labs(panel: LabPanel) -> str:
    """
    Convert raw lab values into a concise, clinically flavored summary.
    """
    statements = []

    # WBC
    if panel.wbc >= 18:
        statements.append(f"WBC {panel.wbc} - critically high, suggests severe infection.")
    elif panel.wbc >= 11:
        statements.append(f"WBC {panel.wbc} - elevated, possible infection or stress.")
    else:
        statements.append(f"WBC {panel.wbc} - within normal range.")

    # Lactate
    if panel.lactate >= 4:
        statements.append(
            f"Lactate {panel.lactate} - markedly elevated, concerning for tissue hypoperfusion."
        )
    elif panel.lactate >= 2:
        statements.append(
            f"Lactate {panel.lactate} - mildly elevated, may indicate early hypoperfusion."
        )
    else:
        statements.append(f"Lactate {panel.lactate} - within normal range.")

    # Creatinine
    if panel.creatinine >= 2:
        statements.append(
            f"Creatinine {panel.creatinine} - significantly elevated, suggests acute kidney injury."
        )
    elif panel.creatinine >= 1.3:
        statements.append(
            f"Creatinine {panel.creatinine} - mildly elevated, possible renal dysfunction."
        )
    else:
        statements.append(f"Creatinine {panel.creatinine} - within normal range.")

    return " ".join(statements)


def summarize_vitals_trend(points: List[VitalPoint]) -> str:
    """
    Convert a series of vitals into a high-level narrative about trends.
    """
    if not points:
        return "No vitals data available."

    start, end = points[0], points[-1]

    spo2_trend = _describe_trend(start.spo2, end.spo2, "SpO2")
    hr_trend = _describe_trend(start.heart_rate, end.heart_rate, "heart rate")
    rr_trend = _describe_trend(
        start.respiratory_rate,
        end.respiratory_rate,
        "respiratory rate",
    )

    return (
        f"Over the observed period from {start.time} to {end.time}: "
        f"{spo2_trend} {hr_trend} {rr_trend}"
    )


def _describe_trend(start_value: float, end_value: float, label: str) -> str:
    delta = end_value - start_value

    if abs(delta) < 1:
        direction = "remained stable"
    elif delta < 0:
        direction = "declined"
    else:
        direction = "increased"

    return (
        f"{label} {direction} from {start_value:.1f} to {end_value:.1f}. "
    )


def mock_lab_panel() -> LabPanel:
    """
    Provide a mock LabPanel for demo purposes.
    """
    return LabPanel(wbc=18.5, lactate=4.8, creatinine=2.1)


def mock_vitals_series() -> List[VitalPoint]:
    """
    Provide mock vitals time-series data for demo purposes.
    """
    return [
        VitalPoint(time="T0", spo2=95, heart_rate=105, respiratory_rate=20),
        VitalPoint(time="T30", spo2=92, heart_rate=112, respiratory_rate=24),
        VitalPoint(time="T60", spo2=89, heart_rate=118, respiratory_rate=26),
        VitalPoint(time="T90", spo2=88, heart_rate=122, respiratory_rate=28),
    ]




