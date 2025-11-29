"""
Hour 7-8: Standalone verification script for MCTA agent logic.

This script tests the multi-turn function calling pipeline outside of Streamlit
to verify that the agent correctly:
1. Receives multimodal input
2. Calls both tools (calculate_sepsis_risk and generate_vitals_visualization)
3. Returns structured JSON output

Run with: python verify_agent.py
"""

import base64
import json
import os
from dotenv import load_dotenv

from utils import run_triage_agent

# Load environment variables
load_dotenv()

# Verify API key is set
if not os.getenv("GEMINI_API_KEY"):
    print("❌ ERROR: GEMINI_API_KEY not found in environment.")
    print("   Please set it in a .env file or export it in your shell.")
    exit(1)

print("=" * 70)
print("MCTA Agent Verification Script")
print("=" * 70)
print()

# Define high-risk multimodal input scenario
print("📋 Setting up high-risk scenario...")
print()

# Mock text notes (high-risk sepsis scenario)
mock_notes = """
Patient presents with:
- Severe shortness of breath starting 2 hours ago
- Chest pain and rapid heart rate
- Fever and chills
- Patient appears distressed and diaphoretic
- History of recent infection
"""

# Mock base64 image (small 1x1 red pixel PNG for testing)
# In real usage, this would be a full X-ray/CT scan
mock_image_base64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
mock_image_mime = "image/png"

# High-risk mock labs (critically high WBC, elevated lactate)
mock_labs = {
    "WBC_count": 19.5,  # Critically high
    "Lactate_level": 4.8,  # Elevated
    "Troponin": 0.08,
    "Hemoglobin": 12.8,
}

# High-risk mock vitals (declining SpO2, increasing HR)
mock_vitals = [
    {"time": "00:00", "SpO2": 98, "HeartRate": 75},
    {"time": "01:00", "SpO2": 94, "HeartRate": 90},
    {"time": "02:00", "SpO2": 88, "HeartRate": 110},
    {"time": "03:00", "SpO2": 85, "HeartRate": 125},  # Critical deterioration
]

print("✅ Mock data prepared:")
print(f"   - Text notes: {len(mock_notes)} characters")
print(f"   - Image: {len(mock_image_base64)} base64 characters ({mock_image_mime})")
print(f"   - Labs: WBC={mock_labs['WBC_count']}, Lactate={mock_labs['Lactate_level']}")
print(f"   - Vitals: {len(mock_vitals)} time points")
print()

# Run the triage agent
print("🚀 Running MCTA triage agent...")
print()

try:
    report, raw_json_text, tool_logs, errors = run_triage_agent(
        user_input_text=mock_notes,
        uploaded_image_base64=mock_image_base64,
        uploaded_image_mime=mock_image_mime,
        labs_json=mock_labs,
        vitals_list=mock_vitals,
    )

    print("=" * 70)
    print("FUNCTION CALL LOG (Multi-Turn Exchange)")
    print("=" * 70)
    for log in tool_logs:
        print(f"  {log}")
    print()

    if errors:
        print("=" * 70)
        print("ERRORS")
        print("=" * 70)
        for error in errors:
            print(f"  ❌ {error}")
        print()

    if report:
        print("=" * 70)
        print("FINAL DIAGNOSTIC REPORT (Parsed JSON)")
        print("=" * 70)
        print(json.dumps(report, indent=2))
        print()

        # Verify key fields
        print("=" * 70)
        print("VERIFICATION CHECKS")
        print("=" * 70)
        
        checks_passed = 0
        total_checks = 6

        # Check 1: Triage urgency exists
        if "triage_urgency" in report:
            urgency = report["triage_urgency"]
            if urgency in ["RED", "YELLOW", "GREEN"]:
                print(f"  ✅ Triage urgency: {urgency}")
                checks_passed += 1
            else:
                print(f"  ❌ Invalid triage urgency: {urgency}")
        else:
            print("  ❌ Missing triage_urgency field")

        # Check 2: Differential diagnosis exists
        if "differential_diagnosis" in report:
            diff = report["differential_diagnosis"]
            if isinstance(diff, list) and len(diff) > 0:
                print(f"  ✅ Differential diagnosis: {len(diff)} hypotheses")
                checks_passed += 1
            else:
                print("  ❌ Invalid or empty differential_diagnosis")
        else:
            print("  ❌ Missing differential_diagnosis field")

        # Check 3: Confidence score exists
        if "confidence_score" in report:
            conf = report["confidence_score"]
            if isinstance(conf, (int, float)) and 0 <= conf <= 1:
                print(f"  ✅ Confidence score: {conf:.2f}")
                checks_passed += 1
            else:
                print(f"  ❌ Invalid confidence score: {conf}")
        else:
            print("  ❌ Missing confidence_score field")

        # Check 4: Evidence summary exists
        if "evidence_summary" in report:
            evidence = report["evidence_summary"]
            if isinstance(evidence, str) and len(evidence) > 0:
                print(f"  ✅ Evidence summary: {len(evidence)} characters")
                checks_passed += 1
            else:
                print("  ❌ Invalid or empty evidence_summary")
        else:
            print("  ❌ Missing evidence_summary field")

        # Check 5: Tool verification data exists
        if "tool_verification_data" in report:
            tvd = report["tool_verification_data"]
            if isinstance(tvd, dict):
                print(f"  ✅ Tool verification data present")
                # Check for risk score
                if any("risk" in str(k).lower() or "score" in str(k).lower() for k in tvd.keys()):
                    print(f"     - Risk score data found")
                # Check for visualization
                if any("visual" in str(k).lower() or "image" in str(k).lower() or "base64" in str(k).lower() for k in tvd.keys()):
                    print(f"     - Visualization data found")
                checks_passed += 1
            else:
                print("  ❌ Invalid tool_verification_data format")
        else:
            print("  ❌ Missing tool_verification_data field")

        # Check 6: Tools were called (check logs)
        tool_calls_found = any("calculate_sepsis_risk" in log for log in tool_logs)
        viz_calls_found = any("generate_vitals_visualization" in log for log in tool_logs)
        if tool_calls_found and viz_calls_found:
            print(f"  ✅ Both tools were called (sepsis risk + visualization)")
            checks_passed += 1
        elif tool_calls_found:
            print(f"  ⚠️  Only sepsis risk tool was called")
            checks_passed += 0.5
        else:
            print(f"  ❌ No tool calls detected in logs")

        print()
        print("=" * 70)
        print(f"VERIFICATION RESULT: {checks_passed}/{total_checks} checks passed")
        print("=" * 70)
        
        if checks_passed >= 5:
            print("✅ Agent verification SUCCESSFUL!")
        elif checks_passed >= 3:
            print("⚠️  Agent verification PARTIAL (some issues detected)")
        else:
            print("❌ Agent verification FAILED (critical issues detected)")

    else:
        print("=" * 70)
        print("❌ VERIFICATION FAILED: No diagnostic report generated")
        print("=" * 70)
        if errors:
            print("Errors encountered:")
            for error in errors:
                print(f"  - {error}")

    if raw_json_text:
        print()
        print("=" * 70)
        print("RAW JSON RESPONSE (First 500 characters)")
        print("=" * 70)
        print(raw_json_text[:500] + "..." if len(raw_json_text) > 500 else raw_json_text)
        print()

except Exception as e:
    print("=" * 70)
    print("❌ EXCEPTION OCCURRED")
    print("=" * 70)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=" * 70)
print("Verification script completed.")
print("=" * 70)


