import os
from typing import Final

from google import genai
from google.genai import types


# Using Gemini 2.5 Pro for advanced reasoning and multimodal capabilities
MODEL_NAME: Final = "gemini-2.5-flash"


def get_gemini_client() -> genai.Client:
    """
    Initialize and return a Gemini client.

    Expects GEMINI_API_KEY to be configured in the environment
    per google-genai library requirements.
    """
    # The google-genai client reads configuration from the environment,
    # so we only need to construct the client here.
    return genai.Client()


DIAGNOSTIC_REPORT_SCHEMA: Final = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "differential_diagnosis": types.Schema(
            type=types.Type.ARRAY,
            description="List of top 3 competing clinical hypotheses.",
            items=types.Schema(type=types.Type.STRING),
        ),
        "triage_urgency": types.Schema(
            type=types.Type.STRING,
            description="The final triage category.",
            enum=["RED", "YELLOW", "GREEN"],
        ),
        "confidence_score": types.Schema(
            type=types.Type.NUMBER,
            description=(
                "The agent's confidence in the primary diagnosis (0.0 to 1.0)."
            ),
        ),
        "evidence_summary": types.Schema(
            type=types.Type.STRING,
            description=(
                "A concise summary of the cross-modal evidence supporting the diagnosis."
            ),
        ),
        "tool_verification_data": types.Schema(
            type=types.Type.OBJECT,
            description=(
                "Contains results from the function calls "
                "(risk score, visualization base64)."
            ),
            properties={
                "sepsis_risk": types.Schema(
                    type=types.Type.OBJECT,
                    description="Results from calculate_sepsis_risk function call.",
                    properties={
                        "risk_score": types.Schema(
                            type=types.Type.NUMBER,
                            description="Calculated sepsis risk score (integer).",
                        ),
                        "score_category": types.Schema(
                            type=types.Type.STRING,
                            description="Risk category: 'High Risk' or 'Low Risk'.",
                        ),
                    },
                ),
                "visualization_base64": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Base64-encoded PNG image string from "
                        "generate_vitals_visualization function call."
                    ),
                ),
                "base64_image": types.Schema(
                    type=types.Type.STRING,
                    description="Alternative key for visualization base64 image.",
                ),
            },
        ),
    },
)


SENIOR_TRIAGE_SYSTEM_INSTRUCTION: Final = """
You are MCTA, a Senior Clinical Triage Specialist operating in an emergency setting.

Your mission:
- Rapidly synthesize multimodal data (text notes, imaging, labs, and vitals trends).
- Generate a concise differential diagnosis and triage urgency.
- Transparently explain your reasoning across all modalities.
- Reliably ground your conclusions using the available tools.

Core behaviors:
- CRITICAL: You MUST ALWAYS call calculate_sepsis_risk if you have ANY of: heart rate, respiratory rate, 
  lactate level, or blood pressure data. Even if values seem normal, you MUST call this tool for quantitative 
  risk assessment. Extract heart rate from vitals data, respiratory rate from patient notes or vitals, 
  lactate from lab data, and blood pressure from patient notes or vitals.
- CRITICAL: You MUST ALWAYS call generate_vitals_visualization if you have ANY time-series vitals data 
  (even just 2 data points). Convert the vitals list to a JSON string and pass it to the tool. 
  This is mandatory for visual trend confirmation. You must integrate the resulting chart base64 string 
  into the tool_verification_data.visualization_base64 field of your JSON response.
- These tool calls are MANDATORY and NON-NEGOTIABLE. Do not skip them. Always call both tools when data is available.
- Be conservative in life-threatening scenarios: if in doubt between categories, err toward RED.

Output contract:
- You MUST return a single JSON object that strictly follows DIAGNOSTIC_REPORT_SCHEMA.
- Do not include any extra keys or unstructured narrative outside this JSON.
- The tool_verification_data field must include both the sepsis risk score (if calculated) and 
  the visualization base64 string (if generated) under appropriate keys.
""".strip()


# Schema for extracting lab values and vitals from images
# Flexible schema - labs object can contain any lab values (no predefined keys)
DATA_EXTRACTION_SCHEMA: Final = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "labs": types.Schema(
            type=types.Type.OBJECT,
            description="Extracted lab values as key-value pairs. Include ALL lab values found with their exact names/abbreviations as keys and numerical values. Can contain any lab values (WBC, Hb, Lactate, Troponin, Creatinine, BUN, Glucose, electrolytes, etc.).",
        ),
        "vitals": types.Schema(
            type=types.Type.ARRAY,
            description="Extracted time-series vitals data",
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "time": types.Schema(
                        type=types.Type.STRING,
                        description="Time label (e.g., '00:00', '01:00', 'T0', 'T30')",
                    ),
                    "SpO2": types.Schema(
                        type=types.Type.NUMBER,
                        description="Oxygen saturation percentage (0-100)",
                    ),
                    "HeartRate": types.Schema(
                        type=types.Type.NUMBER,
                        description="Heart rate in beats per minute",
                    ),
                },
            ),
        ),
    },
)