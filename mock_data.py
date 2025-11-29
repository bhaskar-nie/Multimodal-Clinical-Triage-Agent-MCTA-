"""
Mock data for MCTA demonstration.

This module provides sample lab and vitals data in JSON format
for testing the data abstraction layer.
"""

import json

# Default healthy/normal patient state (Green Triage) - Initial state of the app
DEFAULT_LABS_JSON = {
    "WBC_count": 7.5,  # Normal range: 4.0-11.0
    "Lactate_level": 1.2,  # Normal range: 0.5-2.2
    "Troponin": 0.01,  # Normal: <0.04
    "Hemoglobin": 14.5,  # Normal range: 12.0-16.0 (female) / 13.5-17.5 (male)
}

# Default healthy vitals time-series data
DEFAULT_VITALS_TIMESERIES_JSON = [
    {"time": "00:00", "SpO2": 98, "HeartRate": 72},
    {"time": "01:00", "SpO2": 98, "HeartRate": 70},
    {"time": "02:00", "SpO2": 99, "HeartRate": 68},
    {"time": "03:00", "SpO2": 98, "HeartRate": 70},
]

# Legacy mock data (kept for backward compatibility if needed)
MOCK_LABS_JSON = {
    "WBC_count": 18.5,
    "Lactate_level": 4.2,
    "Troponin": 0.05,
    "Hemoglobin": 13.5,
}

MOCK_VITALS_TIMESERIES_JSON = [
    {"time": "00:00", "SpO2": 98, "HeartRate": 75},
    {"time": "01:00", "SpO2": 95, "HeartRate": 85},
    {"time": "02:00", "SpO2": 90, "HeartRate": 105},
    {"time": "03:00", "SpO2": 88, "HeartRate": 115},
]

# Simple pre-processed summaries to simulate Hour 2-3 output for context
SIMULATED_TABULAR_SUMMARY = (
    "Current lab results show a critically high WBC count (18.5) "
    "and elevated lactate (4.2), indicating severe systemic inflammation."
)

SIMULATED_TIMESERIES_TREND = (
    "Vitals trend shows progressive deterioration: SpO2 dropped from 98% to 88% "
    "and Heart Rate increased sharply from 75 to 115 over the last three hours."
)


def get_default_data():
    """
    Return a dictionary containing default healthy patient data (Green Triage state).
    
    Returns:
        Dictionary with keys: labs, vitals
    """
    return {
        "labs": DEFAULT_LABS_JSON.copy(),
        "vitals": [v.copy() for v in DEFAULT_VITALS_TIMESERIES_JSON],
    }


def get_mock_data():
    """
    Return a dictionary containing all mock data for the MCTA demo.
    
    Returns:
        Dictionary with keys: labs, vitals, tabular_summary, timeseries_summary
    """
    return {
        "labs": MOCK_LABS_JSON,
        "vitals": MOCK_VITALS_TIMESERIES_JSON,
        "tabular_summary": SIMULATED_TABULAR_SUMMARY,
        "timeseries_summary": SIMULATED_TIMESERIES_TREND,
    }

