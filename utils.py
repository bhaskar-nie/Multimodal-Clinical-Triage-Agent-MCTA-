import base64
import json
import time
from typing import Any, Dict, List, Tuple

from google.genai import types
from google.genai.errors import APIError
from config import (
    DATA_EXTRACTION_SCHEMA,
    DIAGNOSTIC_REPORT_SCHEMA,
    MODEL_NAME,
    SENIOR_TRIAGE_SYSTEM_INSTRUCTION,
    get_gemini_client,
)
from tools import TOOL_CONFIG, calculate_sepsis_risk, generate_vitals_visualization


def preprocess_tabular_data(labs_json: dict) -> str:
    """
    Convert raw lab JSON data into high-level, interpretive language features.
    
    Uses Gemini to analyze the lab values dynamically, handling any lab values present.
    IMPORTANT: Only analyzes values that are actually present - does not assume or infer missing values.
    """
    if not labs_json or not isinstance(labs_json, dict):
        return "Tabular Data Feature: No lab data available."
    
    # Check if we have any meaningful data (exclude None, 0, empty strings)
    valid_labs = {k: v for k, v in labs_json.items() if v is not None and v != 0 and v != ""}
    
    if not valid_labs:
        return "Tabular Data Feature: No lab data available."
    
    # Use Gemini to analyze the lab values
    client = get_gemini_client()
    if client is None:
        # Fallback to simple summary if client unavailable
        lab_items = [f"{k}: {v}" for k, v in valid_labs.items()]
        return f"Tabular Data Feature: Lab values extracted from image: {', '.join(lab_items)}."
    
    # Build analysis prompt for Gemini - CRITICAL: Only analyze what's present
    labs_text = json.dumps(valid_labs, indent=2)
    analysis_prompt = f"""Analyze ONLY the lab values that are explicitly provided below. Do NOT assume or infer any values that are not present.

Lab Values Extracted from Image:
{labs_text}

CRITICAL INSTRUCTIONS:
- Only analyze the values that are explicitly shown above
- Do NOT mention values that are not in the list (e.g., do not say "WBC is normal" if WBC is not in the list)
- Do NOT make assumptions about normal ranges for values not present
- Focus ONLY on the values that are actually provided
- If a value is present, analyze it clinically
- If a value is not present, do not mention it at all

Provide:
1. A brief summary of ONLY the values that are present
2. Clinical significance of the values shown (if any are abnormal)
3. Overall assessment based ONLY on the provided values

Format your response as: "Tabular Data Feature: [summary of ONLY the values present]. [clinical interpretation if applicable]."

Be concise and accurate. Only discuss values that are explicitly in the list above."""
    
    try:
        import sys
        print("  🔬 Analyzing lab values with Gemini...", file=sys.stderr)
        
        # Call Gemini for analysis
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=analysis_prompt,
        )
        
        # Extract the analysis text (this is a text response, not JSON)
        analysis_text = _get_response_text(response)
        
        if analysis_text:
            # Ensure it starts with "Tabular Data Feature:"
            if not analysis_text.startswith("Tabular Data Feature:"):
                analysis_text = f"Tabular Data Feature: {analysis_text}"
            print(f"  ✅ Lab analysis complete", file=sys.stderr)
            return analysis_text.strip()
        else:
            # Fallback - only list what's actually present
            lab_items = [f"{k}: {v}" for k, v in valid_labs.items()]
            return f"Tabular Data Feature: Lab values extracted from image: {', '.join(lab_items)}."
    
    except Exception as e:  # noqa: BLE001
        import sys
        print(f"  ⚠️  Lab analysis error: {e}", file=sys.stderr)
        # Fallback to simple summary - only list what's actually present
        lab_items = [f"{k}: {v}" for k, v in valid_labs.items()]
        return f"Tabular Data Feature: Lab values extracted from image: {', '.join(lab_items)}."


def preprocess_timeseries_data(vitals_list: list) -> str:
    """
    Convert raw time-series vitals data into a high-level trend summary.
    """
    if not vitals_list or len(vitals_list) < 2:
        return "Time-Series Feature: Insufficient vitals data for trend analysis."
    
    # Filter out entries with None values for meaningful analysis
    valid_vitals = [v for v in vitals_list if v.get("SpO2") is not None or v.get("HeartRate") is not None]
    
    if len(valid_vitals) < 2:
        return "Time-Series Feature: Insufficient valid vitals data for trend analysis."
    
    # Extract first and last measurements
    first = valid_vitals[0]
    last = valid_vitals[-1]
    
    # Calculate total drop in SpO2 (from first to last) - handle None values
    spo2_start = first.get("SpO2")
    spo2_end = last.get("SpO2")
    
    # Calculate total increase in Heart Rate (from first to last) - handle None values
    hr_start = first.get("HeartRate")
    hr_end = last.get("HeartRate")
    
    # Only calculate if we have valid data
    if spo2_start is None or spo2_end is None:
        spo2_drop = None
        spo2_text = "SpO2 data unavailable"
    else:
        spo2_drop = spo2_start - spo2_end  # Total drop (positive value if declining)
        spo2_text = f"SpO2 declined from {spo2_start}% to {spo2_end}%"
    
    if hr_start is None or hr_end is None:
        hr_increase = None
        hr_text = "Heart Rate data unavailable"
    else:
        hr_increase = hr_end - hr_start  # Total increase (positive value if increasing)
        hr_text = f"Heart Rate increased from {hr_start} to {hr_end}"
    
    # Determine time span
    time_start = first.get("time", "00:00")
    time_end = last.get("time", "00:00")
    num_points = len(vitals_list)
    
    # Calculate duration (approximate hours based on number of data points)
    # Assuming hourly intervals for the mock data
    duration_hours = num_points - 1
    if duration_hours == 1:
        duration = "1 hour"
    elif duration_hours < 4:
        duration = f"{duration_hours} hours"
    else:
        duration = f"{duration_hours} measurement intervals"
    
    # Build the summary focusing on progressive deterioration
    if spo2_drop is not None and hr_increase is not None:
        summary = (
            f"Time-Series Feature: Vitals trend shows a progressive deterioration over {duration}. "
            f"{spo2_text} and {hr_text}. "
        )
        
        # Add clinical interpretation based on the rate of deterioration
        if spo2_drop >= 10 and hr_increase >= 30:
            interpretation = "This indicates ongoing respiratory and circulatory distress."
        elif spo2_drop >= 5:
            interpretation = "This indicates developing respiratory compromise."
        elif hr_increase >= 30:
            interpretation = "This indicates significant cardiovascular stress or compensation."
        else:
            interpretation = "This indicates moderate changes requiring close monitoring."
    else:
        # Handle partial data
        summary = f"Time-Series Feature: Vitals trend over {duration}. {spo2_text}. {hr_text}. "
        interpretation = "Partial vitals data available - complete assessment requires all measurements."
    
    return summary + interpretation


def file_to_part(base64_data: str, mime_type: str) -> types.Part:
    """
    Converts base64 data to a Gemini API Part object.
    
    CRITICAL: This is the robust version used for image ingestion.
    """
    return types.Part.from_bytes(
        data=base64.b64decode(base64_data),
        mime_type=mime_type,
    )


def build_patient_contents(
    user_input_text: str,
    uploaded_image_base64: str | None,
    uploaded_image_mime: str | None,
    labs_json: dict | None = None,
    vitals_list: list | None = None,
    image_analysis_text: str | None = None,
) -> List[types.Part]:
    """
    Build multimodal contents array for Gemini API call.
    
    Following Gemini best practices:
    - For single-image prompts, place image first for better results
    - Include all 4 modalities: Text, Image, Tabular Summary, Time-Series Trend
    - Include Gemini's analysis of images for better context
    """
    parts: List[types.Part] = []
    
    # Place image first if present (best practice for single-image prompts)
    if uploaded_image_base64 and uploaded_image_mime:
        parts.append(file_to_part(uploaded_image_base64, uploaded_image_mime))
    
    # Add text notes
    # Use Part(text=...) instead of Part.from_text() for compatibility
    parts.append(types.Part(text=f"Patient Notes: {user_input_text}"))
    
    # Add Gemini's image analysis if available (from previous analysis step)
    if image_analysis_text:
        parts.append(types.Part(text=f"Image Analysis (from Gemini): {image_analysis_text}"))
    
    # Pre-process and add tabular data (labs) - Part 3
    if labs_json:
        tabular_summary = preprocess_tabular_data(labs_json)
        # tabular_summary already includes "Tabular Data Feature:" prefix
        parts.append(types.Part(text=tabular_summary))
    else:
        parts.append(types.Part(text="Tabular Data Feature: No lab data available."))
    
    # Pre-process and add time-series data (vitals) - Part 4
    if vitals_list:
        timeseries_summary = preprocess_timeseries_data(vitals_list)
        # timeseries_summary already includes "Time-Series Feature:" prefix
        parts.append(types.Part(text=timeseries_summary))
    else:
        parts.append(types.Part(text="Time-Series Feature: No vitals data available."))
    
    # Final instruction - Explicitly require tool calls with data extraction guidance
    instruction_parts = []
    
    # Check what data we have and provide specific instructions
    has_vitals = vitals_list and len(vitals_list) >= 2
    has_labs = labs_json and any(v for v in labs_json.values() if v is not None and v != 0)
    has_image_analysis = image_analysis_text and len(image_analysis_text.strip()) > 0
    
    # Always try to call tools if we have ANY data (labs, vitals, or image analysis)
    if has_vitals or has_labs or has_image_analysis:
        instruction_parts.append("CRITICAL TOOL CALLING REQUIREMENTS:")
        
        # Always try to call calculate_sepsis_risk if we have any relevant data
        instruction_parts.append("1. You MUST call calculate_sepsis_risk. Extract parameters from available data:")
        if has_vitals:
            # Extract heart rate from vitals (use average or latest)
            hr_values = [v.get("HeartRate") for v in vitals_list if v.get("HeartRate") is not None]
            if hr_values:
                avg_hr = int(sum(hr_values) / len(hr_values))
                instruction_parts.append(f"   - heart_rate: {avg_hr} (from vitals)")
            else:
                instruction_parts.append("   - heart_rate: Extract from patient notes or image analysis, or use 80 as default")
        else:
            instruction_parts.append("   - heart_rate: Extract from patient notes or image analysis, or use 80 as default")
        
        instruction_parts.append("   - blood_pressure: Extract systolic from patient notes or image analysis (look for 'BP', 'blood pressure', numbers like '120/80') or use 120 as default")
        
        # Try to find lactate in labs (could be under various keys)
        lactate_value = None
        if labs_json:
            for key in ["Lactate_level", "Lactate", "LAC", "Lactic_Acid", "lactate", "lac"]:
                if labs_json.get(key):
                    lactate_value = labs_json.get(key)
                    break
        
        if lactate_value:
            instruction_parts.append(f"   - lactate_level: {lactate_value} (from labs)")
        else:
            instruction_parts.append("   - lactate_level: Extract from patient notes or image analysis, or use 1.0 as default")
        
        instruction_parts.append("   - respiratory_rate: Extract from patient notes or image analysis (look for 'RR', 'respiratory rate', 'breathing rate') or use 16 as default")
        
        # Call visualization if we have vitals OR if image analysis mentions vitals
        if has_vitals:
            instruction_parts.append("2. You MUST call generate_vitals_visualization. Convert the vitals list to JSON string:")
            instruction_parts.append(f"   - time_series_data: JSON string of {len(vitals_list)} vitals measurements")
            instruction_parts.append("   - Example format: '[{\"time\":\"00:00\",\"SpO2\":98,\"HeartRate\":72},...]'")
        elif has_image_analysis and any(term in image_analysis_text.lower() for term in ["spo2", "heart rate", "hr", "vitals"]):
            instruction_parts.append("2. You MUST call generate_vitals_visualization if you can extract vitals from the image analysis or patient notes.")
            instruction_parts.append("   - Convert vitals to JSON string format: '[{\"time\":\"00:00\",\"SpO2\":98,\"HeartRate\":72},...]'")
        
        instruction_parts.append("3. After calling the tools, synthesize all data and provide your final JSON report.")
        instruction_parts.append("4. Include tool results in tool_verification_data field:")
        instruction_parts.append("   - sepsis_risk: {risk_score: <number>, score_category: 'High Risk' or 'Low Risk'}")
        instruction_parts.append("   - visualization_base64: <base64 string from generate_vitals_visualization>")
    else:
        instruction_parts.append("You have limited data. If you can extract any vitals or lab values from patient notes or image analysis, call the appropriate tools.")
    
    instruction_text = "\n".join(instruction_parts)
    parts.append(types.Part(text=instruction_text))

    return parts


def execute_function_call(func_name: str, func_args: dict, tool_logs: List[str]) -> types.Part:
    """
    Execute a function call and return a Part object with the result.
    """
    # Find the function in TOOL_CONFIG
    func = None
    for tool_func in TOOL_CONFIG:
        if tool_func.__name__ == func_name:
            func = tool_func
            break

    if func is None:
        error_msg = f"Function {func_name} not found in TOOL_CONFIG"
        tool_logs.append(f"[ERROR] {error_msg}")
        # Return error response part
        return types.Part(text=json.dumps({"error": error_msg}))

    # Execute the function
    try:
        result = func(**func_args)
        
        # Log the execution result
        tool_logs.append(f"[OBSERVATION] Host executed {func_name}: {result}")
        
        # Create function response part
        try:
            # Primary method: use from_function_response (per docs)
            if hasattr(types.Part, "from_function_response"):
                return types.Part.from_function_response(
                    name=func_name,
                    response={"result": result},
                )
            # Fallback (for older SDK versions)
            return types.Part(
                text=json.dumps({"function": func_name, "result": result})
            )
        except Exception as e:  # noqa: BLE001
            # Ultimate fallback
            return types.Part(
                text=f"Function {func_name} returned: {json.dumps(result)}"
            )
    except Exception as e:  # noqa: BLE001
        error_msg = f"Execution of {func_name} failed: {e}"
        tool_logs.append(f"[ERROR] {error_msg}")
        return types.Part(text=json.dumps({"error": error_msg}))


def run_triage_agent(
    user_input_text: str,
    uploaded_image_base64: str | None,
    uploaded_image_mime: str | None,
    labs_json: dict | None = None,
    vitals_list: list | None = None,
    image_analysis_text: str | None = None,
) -> Tuple[Dict[str, Any] | None, str | None, List[str], List[str]]:
    """
    Main agent function to execute the multi-turn function calling loop.
    Implements Dynamic Config fix for 400 INVALID_ARGUMENT (JSON/Tools conflict).
    """
    client = get_gemini_client()
    
    if client is None:
        raise ValueError("Gemini Client is not initialized.")

    initial_contents = build_patient_contents(
        user_input_text, uploaded_image_base64, uploaded_image_mime, labs_json, vitals_list, image_analysis_text
    )
    
    # --- Configs for Dynamic Switching ---
    
    # 1. Config for Function Calling (Tools ON, JSON OFF) - For Turns 1, 3, etc.
    config_tool_turn = types.GenerateContentConfig(
        system_instruction=SENIOR_TRIAGE_SYSTEM_INSTRUCTION,
        tools=TOOL_CONFIG, 
        # response_mime_type and response_schema omitted
    )
    # 2. Config for Final JSON Output (Tools OFF, JSON ON) - For Final Turn
    config_json_turn = types.GenerateContentConfig(
        system_instruction=SENIOR_TRIAGE_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=DIAGNOSTIC_REPORT_SCHEMA,
        # tools omitted
    )

    MAX_TURNS = 5
    MAX_RETRIES = 5  # For exponential backoff
    tool_logs: List[str] = []
    errors: List[str] = []
    current_contents = initial_contents
    function_responses_added = False  # Track if we just added function responses
    json_config_attempted = False  # Track if we've already tried JSON config
    last_response = None  # Track last response for final fallback
    
    # --- Multi-Turn Loop ---
    import sys
    print("🔄 Starting multi-turn agent loop...", file=sys.stderr)
    
    for turn_count in range(MAX_TURNS):
        
        # === Dynamic Configuration Strategy (FIX FOR 400 ERROR) ===
        # Priority: If function responses were added, use JSON config.
        # Otherwise, if we've already tried JSON config and it failed, try again with explicit instruction.
        # Otherwise, use tool config.
        
        if function_responses_added:
            # If we just added function responses, this is the final synthesis turn.
            current_config = config_json_turn
            function_responses_added = False  # Reset flag
            json_config_attempted = True
            print(f"📝 Turn {turn_count}: Generating final JSON report...", file=sys.stderr)
        elif json_config_attempted and turn_count >= 2:
            # If we've already tried JSON config but didn't get a response, try again with explicit instruction
            current_config = config_json_turn
            print(f"📝 Turn {turn_count}: Retrying JSON generation...", file=sys.stderr)
        else:
            # Otherwise, we keep tools active and expect a tool request or intermediate text.
            current_config = config_tool_turn
            print(f"🔧 Turn {turn_count}: Tool calling enabled...", file=sys.stderr)
        # ==========================================================
        
        # --- Exponential Backoff Retry Loop (FIX FOR 429) ---
        response = None
        for retry_attempt in range(MAX_RETRIES):
            try:
                # 1. Call Gemini API
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=current_contents,
                    config=current_config,
                )
                last_response = response  # Store for potential final fallback
                break  # Success
            
            except APIError as e:
                # Handle API errors (429, 500, etc.)
                # Check error code/message to determine if it's retryable
                error_str = str(e).lower()
                is_retryable = (
                    "429" in error_str or 
                    "resource_exhausted" in error_str or 
                    "quota" in error_str or
                    "500" in error_str or
                    "internal" in error_str or
                    "server" in error_str
                )
                
                if is_retryable and retry_attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** retry_attempt + (time.time() % 1)
                    # Do not log retry attempts to console, only to tool_logs
                    tool_logs.append(f"[ERROR] API Quota/Server Error. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    errors.append(f"Fatal API Error after {MAX_RETRIES} retries: {e.__class__.__name__} - {str(e)}")
                    return None, f"Error: {str(e)}", tool_logs, errors
            except Exception as e:
                errors.append(f"Unexpected Error: {str(e)}")
                return None, "Error: Unexpected Runtime Issue.", tool_logs, errors
        
        if response is None:
            break  # Exit if all retries failed
        
        # Safely extract the candidate content
        candidate = response.candidates[0]
        model_content = getattr(candidate, 'content', None)
        
        # 2. Detect Function Calls
        function_calls = []
        if model_content and model_content.parts:
            for part in model_content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part.function_call)
        
        if function_calls:
            print(f"  → Model requested {len(function_calls)} function call(s)", file=sys.stderr)
        
        # 5. Final Response Detection
        if not function_calls:
            # If no function calls are requested, try to extract and parse JSON response
            raw_json_text = None
            try:
                raw_json_text = _get_raw_json_text(response)
            except Exception as e:  # noqa: BLE001
                tool_logs.append(f"[Turn {turn_count}] Could not extract text from response: {e}")
            
            # Try to parse as JSON regardless of config
            if raw_json_text and raw_json_text.strip():
                # Try to extract JSON from the text (might be wrapped in markdown code blocks)
                json_text = raw_json_text.strip()
                # Remove markdown code blocks if present
                if json_text.startswith("```json"):
                    json_text = json_text[7:]  # Remove ```json
                if json_text.startswith("```"):
                    json_text = json_text[3:]  # Remove ```
                if json_text.endswith("```"):
                    json_text = json_text[:-3]  # Remove closing ```
                json_text = json_text.strip()
                
                # Only try to parse if we have non-empty content
                if json_text:
                    try:
                        report = json.loads(json_text)
                        # Validate that it has required fields
                        if isinstance(report, dict) and "triage_urgency" in report:
                            tool_logs.append(f"[Turn {turn_count}] Final response received and parsed as JSON.")
                            print(f"✅ Successfully parsed JSON response on turn {turn_count}", file=sys.stderr)
                            return report, json_text, tool_logs, errors
                    except json.JSONDecodeError as e:
                        # Try to repair before giving up
                        repaired = _repair_json(json_text)
                        if not repaired:
                            repaired = _repair_json_aggressive(json_text)
                        if repaired:
                            try:
                                report = json.loads(repaired)
                                if isinstance(report, dict) and "triage_urgency" in report:
                                    tool_logs.append(f"[Turn {turn_count}] Final response received and parsed as JSON (after repair).")
                                    print(f"✅ Successfully parsed JSON response on turn {turn_count} (after repair)", file=sys.stderr)
                                    return report, repaired, tool_logs, errors
                            except json.JSONDecodeError:
                                pass  # Not valid JSON, continue
                        else:
                            print(f"  ⚠️  JSON parse error on turn {turn_count}: {e}", file=sys.stderr)
            
            # If we're in JSON config turn and still no valid JSON, that's an error
            if current_config == config_json_turn:
                errors.append("Final response was not valid JSON despite structured output config.")
                return None, raw_json_text or "No text content", tool_logs, errors
            
            # If model responded with text/no tool call but we're using tool config,
            # this might be the final response (model decided not to use tools)
            # Try to parse it as JSON first
            if model_content and raw_json_text and raw_json_text.strip():
                # Check if it looks like JSON (starts with { or contains triage_urgency)
                json_text_clean = raw_json_text.strip()
                # Remove markdown code blocks if present
                if json_text_clean.startswith("```json"):
                    json_text_clean = json_text_clean[7:].strip()
                if json_text_clean.startswith("```"):
                    json_text_clean = json_text_clean[3:].strip()
                if json_text_clean.endswith("```"):
                    json_text_clean = json_text_clean[:-3].strip()
                
                # Only try to parse if we have non-empty content
                if json_text_clean and (json_text_clean.startswith("{") or "triage_urgency" in json_text_clean):
                    try:
                        report = json.loads(json_text_clean)
                        if isinstance(report, dict) and "triage_urgency" in report:
                            tool_logs.append(f"[Turn {turn_count}] Final response received (parsed as JSON from text).")
                            return report, json_text_clean, tool_logs, errors
                    except json.JSONDecodeError as e:
                        # Try to repair malformed JSON - use both repair functions
                        repaired_json = _repair_json(json_text_clean)
                        if not repaired_json:
                            # Try aggressive repair if regular repair fails
                            repaired_json = _repair_json_aggressive(json_text_clean)
                        
                        if repaired_json:
                            try:
                                report = json.loads(repaired_json)
                                if isinstance(report, dict) and "triage_urgency" in report:
                                    tool_logs.append(f"[Turn {turn_count}] Successfully parsed JSON after repair.")
                                    print(f"  ✅ JSON repaired and parsed successfully on turn {turn_count}", file=sys.stderr)
                                    return report, repaired_json, tool_logs, errors
                            except json.JSONDecodeError:
                                pass
                        
                        # Only log error if we actually have content to parse (but don't show in UI)
                        if json_text_clean:
                            # Log to stderr but not to tool_logs (user doesn't want to see these)
                            print(f"  ⚠️  JSON parse error on turn {turn_count}: {e}", file=sys.stderr)
                            print(f"  🔄 Attempting JSON repair...", file=sys.stderr)
                        else:
                            tool_logs.append(f"[Turn {turn_count}] Empty response received.")
                
                # If not valid JSON and we haven't tried JSON config yet, switch to it
                if not json_config_attempted:
                    # Don't log this to tool_logs (user doesn't want to see it)
                    print(f"  🔄 Turn {turn_count}: Switching to JSON config...", file=sys.stderr)
                    # Add the model's response to history
                    current_contents = list(current_contents) + [model_content]
                    # Add explicit JSON instruction
                    json_instruction = types.Part(
                        text="Please provide your final diagnostic report as a JSON object only (no markdown, no explanation) with this exact structure: {\"differential_diagnosis\": [\"...\"], \"triage_urgency\": \"RED|YELLOW|GREEN\", \"confidence_score\": 0.0-1.0, \"evidence_summary\": \"...\", \"tool_verification_data\": {...}}"
                    )
                    current_contents.append(types.Content(role="user", parts=[json_instruction]))
                    # Force JSON config on next turn
                    json_config_attempted = True
                    continue
                else:
                    # We've already tried JSON config, this is likely the best we can get
                    print(f"  🔄 Turn {turn_count}: Attempting to extract JSON from text...", file=sys.stderr)
                    # Try one more time to extract JSON from the text
                    try:
                        # Look for JSON object in the text
                        start_idx = json_text_clean.find("{")
                        end_idx = json_text_clean.rfind("}")
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            json_extract = json_text_clean[start_idx:end_idx+1]
                            # Try to repair if parsing fails
                            try:
                                report = json.loads(json_extract)
                            except json.JSONDecodeError:
                                json_extract = _repair_json(json_extract)
                                if not json_extract:
                                    json_extract = _repair_json_aggressive(json_extract)
                                if json_extract:
                                    report = json.loads(json_extract)
                                else:
                                    raise
                            
                            if isinstance(report, dict) and "triage_urgency" in report:
                                tool_logs.append(f"[Turn {turn_count}] Successfully extracted JSON from text response.")
                                return report, json_extract, tool_logs, errors
                    except Exception:  # noqa: BLE001
                        pass
                    
                    # Last resort: return what we have with a warning
                    errors.append("Could not parse final response as valid JSON. Returning raw text.")
                    return None, raw_json_text, tool_logs, errors
            else:
                errors.append(f"Model returned empty or invalid content on turn {turn_count}.")
                return None, None, tool_logs, errors

        # --- Function Call Turn (Turn 1, 3, etc.) ---
        
        tool_logs.append(f"[Turn {turn_count}] Model requested {len(function_calls)} function call(s).")
        
        function_response_parts = []
        
        # 3. Execute Functions
        for call in function_calls:
            func_name = getattr(call, "name", "")
            func_args = getattr(call, "args", {}) or {}
            
            # Log Model's Request
            tool_logs.append(f"[ACTION] Model requested: {func_name}({json.dumps(func_args)})")
            print(f"  🔧 Executing: {func_name}({json.dumps(func_args)})", file=sys.stderr)
            
            # Execute Python function and get result part
            response_part = execute_function_call(func_name, func_args, tool_logs)
            function_response_parts.append(response_part)
            print(f"  ✅ Function {func_name} executed successfully", file=sys.stderr)
            
        # 4. Conversation History Update (Feed results back)
        
        # 4a. Append model's request content (contains function calls)
        current_contents = list(current_contents)
        current_contents.append(model_content)
        # 4b. Append function response as user content (Observation)
        function_response_content = types.Content(
            role="user",
            parts=function_response_parts,
        )
        current_contents.append(function_response_content)
        
        # 4c. Add explicit instruction to return JSON after receiving tool results
        json_instruction_part = types.Part(
            text="Now that you have the tool results, provide your final diagnostic report as a JSON object only (no markdown code blocks, no explanation text). The JSON must have this exact structure: {\"differential_diagnosis\": [\"...\"], \"triage_urgency\": \"RED|YELLOW|GREEN\", \"confidence_score\": 0.0-1.0, \"evidence_summary\": \"...\", \"tool_verification_data\": {...}}. Include the tool results in the tool_verification_data field."
        )
        current_contents.append(types.Content(role="user", parts=[json_instruction_part]))
        function_responses_added = True  # Mark that we've added function responses
        
    # If loop finishes without returning (too many turns)
    # Last attempt: try to get any response from the last API call
    if last_response is not None:
        try:
            raw_json_text = _get_raw_json_text(last_response)
            # Try to extract JSON one more time
            json_text_clean = raw_json_text.strip()
            # Remove markdown code blocks
            if json_text_clean.startswith("```json"):
                json_text_clean = json_text_clean[7:].strip()
            if json_text_clean.startswith("```"):
                json_text_clean = json_text_clean[3:].strip()
            if json_text_clean.endswith("```"):
                json_text_clean = json_text_clean[:-3].strip()
            
            # Try to find and parse JSON object
            start_idx = json_text_clean.find("{")
            end_idx = json_text_clean.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_extract = json_text_clean[start_idx:end_idx+1]
                try:
                    report = json.loads(json_extract)
                except json.JSONDecodeError:
                    # Try to repair
                    repaired = _repair_json(json_extract)
                    if repaired:
                        try:
                            report = json.loads(repaired)
                            json_extract = repaired
                        except json.JSONDecodeError:
                            pass
                    else:
                        report = None
                
                if report and isinstance(report, dict):
                    tool_logs.append(f"[Final Attempt] Extracted JSON from last response after {MAX_TURNS} turns.")
                    errors.append(f"Warning: Maximum turns reached, but extracted partial response.")
                    return report, json_extract, tool_logs, errors
        except Exception:  # noqa: BLE001
            pass
    
    errors.append(f"Maximum turns ({MAX_TURNS}) reached without final response.")
    tool_logs.append(f"[ERROR] Loop completed {MAX_TURNS} turns without valid JSON response.")
    return None, None, tool_logs, errors


def _get_raw_json_text(response: Any) -> str:
    """
    Helper to extract raw JSON text from the Gemini response.
    
    Returns the raw JSON string before parsing.
    """
    # Try response.text if present
    text = getattr(response, "text", None)
    if not text and getattr(response, "candidates", None):
        # Fallback: join all text parts from the first candidate
        parts = getattr(response.candidates[0].content, "parts", [])
        text_chunks = []
        for p in parts:
            if hasattr(p, "text") and p.text:
                text_chunks.append(p.text)
        text = "\n".join(text_chunks)

    if not text:
        # Try to parse the text part directly from the candidate structure if no response.text
        try:
            return response.candidates[0].content.parts[0].text
        except:
            raise ValueError("No text content found in Gemini response.")

    return text


def _repair_json_aggressive(json_text: str) -> str | None:
    """
    More aggressive JSON repair that handles complex cases like unterminated strings
    by truncating at the problematic point and closing the structure.
    """
    if not json_text or not json_text.strip():
        return None
    
    try:
        # Find the JSON object start
        start_idx = json_text.find("{")
        if start_idx == -1:
            return None
        
        # Try to find where the unterminated string starts
        # Look for patterns like: "key": "value that is not closed
        lines = json_text.split('\n')
        repaired_lines = []
        found_issue = False
        
        for i, line in enumerate(lines):
            # Check if this line has an unterminated string
            # Count unescaped quotes
            quote_count = 0
            escaped = False
            for char in line:
                if escaped:
                    escaped = False
                    continue
                if char == '\\':
                    escaped = True
                    continue
                if char == '"':
                    quote_count += 1
            
            # If odd number of quotes and line doesn't end with quote, it's likely unterminated
            if quote_count % 2 == 1 and not line.rstrip().endswith('"'):
                # Try to close the string at the end of the line
                if line.strip().endswith(','):
                    # Remove trailing comma and add closing quote and comma
                    line = line.rstrip().rstrip(',') + '",'
                elif ':' in line and not line.strip().endswith('"'):
                    # This is a key-value pair with unterminated value
                    # Find the colon and close the string after it
                    colon_idx = line.find(':')
                    if colon_idx != -1:
                        value_part = line[colon_idx+1:].strip()
                        if value_part.startswith('"') and not value_part.endswith('"'):
                            # Unterminated string value - close it
                            line = line[:colon_idx+1] + ' "' + value_part[1:].rstrip().rstrip(',') + '",'
                found_issue = True
            
            repaired_lines.append(line)
        
        if found_issue:
            repaired = '\n'.join(repaired_lines)
            # Try to close any unclosed braces/brackets
            open_braces = repaired.count('{') - repaired.count('}')
            open_brackets = repaired.count('[') - repaired.count(']')
            if open_braces > 0:
                repaired += '\n' + '}' * open_braces
            if open_brackets > 0:
                repaired += ']' * open_brackets
            
            # Validate
            try:
                json.loads(repaired)
                return repaired
            except:
                pass
        
        return None
    except Exception:  # noqa: BLE001
        return None


def _repair_json(json_text: str) -> str | None:
    """
    Attempt to repair malformed JSON by fixing common issues:
    - Unterminated strings (add closing quote)
    - Unescaped quotes in strings
    - Missing closing braces/brackets
    """
    if not json_text or not json_text.strip():
        return None
    
    try:
        # First, try to find the JSON object boundaries
        start_idx = json_text.find("{")
        if start_idx == -1:
            return None
        
        # Try to find matching closing brace
        brace_count = 0
        in_string = False
        escape_next = False
        end_idx = start_idx
        
        for i in range(start_idx, len(json_text)):
            char = json_text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
        
        if brace_count > 0:
            # Missing closing braces - try to add them
            json_text = json_text[:end_idx+1] + "}" * brace_count
        
        # Try to fix unterminated strings by finding and closing them
        # This is a more robust heuristic - track string state properly
        lines = json_text.split('\n')
        repaired_lines = []
        in_string = False
        escape_next = False
        
        for line in lines:
            repaired_line = ""
            for i, char in enumerate(line):
                if escape_next:
                    repaired_line += char
                    escape_next = False
                    continue
                
                if char == '\\':
                    repaired_line += char
                    escape_next = True
                    continue
                
                if char == '"':
                    repaired_line += char
                    in_string = not in_string
                    continue
                
                repaired_line += char
            
            # If we're still in a string at the end of the line, close it
            if in_string and repaired_line.strip() and not repaired_line.rstrip().endswith('"'):
                # Check if line ends with comma - if so, close string before comma
                if repaired_line.rstrip().endswith(','):
                    repaired_line = repaired_line.rstrip().rstrip(',') + '",'
                else:
                    repaired_line += '"'
                in_string = False
            
            repaired_lines.append(repaired_line)
        
        repaired = '\n'.join(repaired_lines)
        
        # If still in string at the end, close it
        if in_string:
            repaired += '"'
        
        # Validate it's parseable
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            # If still fails, return None to try aggressive repair
            return None
        
    except Exception:  # noqa: BLE001
        # If repair fails, try a simpler approach: extract up to the last valid character
        try:
            # Find the last complete JSON structure
            for i in range(len(json_text), 0, -1):
                try:
                    test_json = json_text[:i]
                    # Try to close it if needed
                    open_braces = test_json.count('{') - test_json.count('}')
                    open_brackets = test_json.count('[') - test_json.count(']')
                    if open_braces > 0:
                        test_json += '}' * open_braces
                    if open_brackets > 0:
                        test_json += ']' * open_brackets
                    json.loads(test_json)
                    return test_json
                except:
                    continue
        except:
            pass
        
        return None


def _get_response_text(response: Any) -> str:
    """
    Helper to extract text from Gemini response (for non-JSON responses).
    Returns empty string if no text found (doesn't raise error).
    """
    # Try response.text if present
    text = getattr(response, "text", None)
    if not text and getattr(response, "candidates", None):
        # Fallback: join all text parts from the first candidate
        parts = getattr(response.candidates[0].content, "parts", [])
        text_chunks = []
        for p in parts:
            if hasattr(p, "text") and p.text:
                text_chunks.append(p.text)
        text = "\n".join(text_chunks)

    if not text:
        # Try to parse the text part directly from the candidate structure
        try:
            return response.candidates[0].content.parts[0].text
        except:
            return ""

    return text


def _parse_json_report(response: Any) -> Dict[str, Any]:
    """
    Helper to parse JSON from the response.

    The new google-genai SDK exposes structured responses, but the spec
    for this project expects a JSON string which we parse here.
    """
    raw_text = _get_raw_json_text(response)
    return json.loads(raw_text)


def extract_data_from_image(
    image_base64: str,
    image_mime: str,
) -> Tuple[Dict[str, Any] | None, List[Dict[str, Any]] | None, str | None, List[str]]:
    """
    Analyze a medical image with Gemini and extract any structured data present.
    Returns Gemini's natural analysis text along with extracted labs/vitals.
    
    Args:
        image_base64: Base64-encoded image string
        image_mime: MIME type of the image (e.g., "image/jpeg", "image/png")
    
    Returns:
        Tuple of (labs_dict, vitals_list, analysis_text, errors)
        - labs_dict: Dictionary with any lab values found (flexible keys)
        - vitals_list: List of dicts with time, SpO2, HeartRate
        - analysis_text: Gemini's natural analysis of the image
        - errors: List of error messages
    """
    client = get_gemini_client()
    errors: List[str] = []
    
    if client is None:
        errors.append("Gemini Client is not initialized.")
        return None, None, None, errors
    
    # Simple prompt - just ask Gemini to analyze the medical image
    extraction_prompt = """Analyze this medical image thoroughly.

If this image contains:
- A LAB REPORT: Extract all lab values (names and numerical values)
- A VITALS CHART: Extract all time-series measurements (time, SpO2, Heart Rate)
- An X-RAY or SCAN: Describe the findings and any visible measurements or annotations
- Any other medical data: Extract all relevant information

Provide a comprehensive analysis of what you see in the image. Include all numerical values, measurements, and clinical findings visible."""

    # Create image part
    image_part = file_to_part(image_base64, image_mime)
    text_part = types.Part(text=extraction_prompt)
    contents = [image_part, text_part]
    
    try:
        import sys
        print("  📸 Analyzing medical image with Gemini (direct extraction)...", file=sys.stderr)
        
        # Send image directly to Gemini with prompt (no schema - let Gemini return JSON naturally)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
        )
        
        # Get Gemini's analysis of the image
        analysis_text = _get_response_text(response)
        
        if not analysis_text or not analysis_text.strip():
            errors.append("No analysis received from Gemini for the image.")
            print("  ⚠️  No analysis from Gemini", file=sys.stderr)
            return None, None, None, errors
        
        print(f"  ✅ Gemini analysis received ({len(analysis_text)} chars)", file=sys.stderr)
        print(f"  📄 Analysis preview: {analysis_text[:200]}...", file=sys.stderr)
        
        # Try to extract structured data (labs/vitals) from the analysis if present
        # But don't force it - if it's just an X-ray analysis, that's fine
        labs_dict = None
        vitals_list = None
        
        # Only try to extract if the analysis mentions labs or vitals
        analysis_lower = analysis_text.lower()
        has_lab_mentions = any(term in analysis_lower for term in ["lab", "wbc", "hemoglobin", "lactate", "troponin", "creatinine", "bun", "glucose"])
        has_vitals_mentions = any(term in analysis_lower for term in ["spo2", "sp o2", "heart rate", "hr", "vitals", "oxygen saturation"])
        
        if has_lab_mentions or has_vitals_mentions:
            print("  🔄 Attempting to extract structured data from analysis...", file=sys.stderr)
            
            extraction_prompt = f"""Based on this medical image analysis, extract any lab values and vitals data:

Image Analysis:
{analysis_text}

Extract and return JSON with:
- "labs": Object with lab names as keys and numerical values (e.g., {{"WBC": 12.5, "Hemoglobin": 14.2}})
- "vitals": Array of objects with time, SpO2, HeartRate (e.g., [{{"time": "00:00", "SpO2": 98, "HeartRate": 72}}])

If the analysis mentions lab values, extract them. If it mentions vitals measurements, extract them.
If no labs/vitals are present (e.g., just X-ray findings), return empty objects/arrays.

Return ONLY valid JSON, no explanation."""
            
            try:
                extract_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=extraction_prompt,
                )
                
                extract_text = _get_response_text(extract_response)
                
                # Try to parse JSON from the extraction response
                json_text = extract_text.strip()
                
                # Remove markdown code blocks if present
                if json_text.startswith("```json"):
                    json_text = json_text[7:].strip()
                elif json_text.startswith("```"):
                    json_text = json_text[3:].strip()
                if json_text.endswith("```"):
                    json_text = json_text[:-3].strip()
                
                # Find JSON object in the text
                start_idx = json_text.find("{")
                end_idx = json_text.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_text = json_text[start_idx:end_idx+1]
                
                parsed_data = json.loads(json_text)
                
                # Extract labs and vitals
                labs_dict = parsed_data.get("labs", {}) or {}
                vitals_list = parsed_data.get("vitals", []) or []
                
                # Clean up labs dict - remove None values
                labs_dict = {k: v for k, v in labs_dict.items() if v is not None and v != 0} if labs_dict else None
                
                # Validate vitals list format
                if vitals_list:
                    validated_vitals = []
                    for v in vitals_list:
                        if isinstance(v, dict) and "time" in v:
                            validated_vitals.append({
                                "time": str(v.get("time", "")),
                                "SpO2": float(v.get("SpO2")) if v.get("SpO2") is not None else None,
                                "HeartRate": int(v.get("HeartRate")) if v.get("HeartRate") is not None else None,
                            })
                    vitals_list = validated_vitals if validated_vitals else None
                else:
                    vitals_list = None
                
                if labs_dict:
                    print(f"  ✅ Extracted {len(labs_dict)} lab values: {list(labs_dict.keys())}", file=sys.stderr)
                if vitals_list:
                    print(f"  ✅ Extracted {len(vitals_list)} vitals measurements", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                # Extraction failed - that's okay, we still have the analysis text
                print(f"  ℹ️  Could not extract structured data ({e}) - using analysis text only", file=sys.stderr)
        
        return labs_dict, vitals_list, analysis_text, errors
        
    except json.JSONDecodeError as e:
        errors.append(f"Failed to parse extracted data as JSON: {e}")
        print(f"  ❌ JSON parsing error: {e}", file=sys.stderr)
        return None, None, None, errors
    except Exception as e:  # noqa: BLE001
        errors.append(f"Error extracting data from image: {e}")
        print(f"  ❌ Extraction error: {e}", file=sys.stderr)
        return None, None, None, errors


def _extract_outputs_with_gemini(
    raw_response_text: str,
    preprocessed_summaries: dict,
    tool_logs: list,
    labs_json: dict | None = None,
    vitals_list: list | None = None,
) -> Dict[str, Any] | None:
    """
    Fallback function: If the main agent doesn't produce valid JSON,
    send the raw response and previous outputs to Gemini with prompts
    to extract diagnosis, reasoning, and risk score.
    
    Args:
        raw_response_text: The raw text response from the main agent
        preprocessed_summaries: Dictionary with "tabular" and "timeseries" summaries
        tool_logs: List of tool call logs
    
    Returns:
        Dictionary with extracted outputs or None if extraction fails
    """
    client = get_gemini_client()
    if client is None:
        return None
    
    if not raw_response_text or not raw_response_text.strip():
        return None
    
    try:
        import sys
        print("  🔄 Sending response to Gemini for fast output extraction...", file=sys.stderr)
        
        # OPTIMIZATION: Truncate very large responses (108k chars is too much!)
        # Extract only the first 5000 chars and last 2000 chars to get key info
        if len(raw_response_text) > 10000:
            print(f"  ⚡ Truncating large response ({len(raw_response_text)} chars) for faster processing...", file=sys.stderr)
            # Try to find JSON object in the response
            json_start = raw_response_text.find("{")
            json_end = raw_response_text.rfind("}")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                # Extract JSON portion (likely the most important part)
                json_portion = raw_response_text[json_start:json_end+1]
                if len(json_portion) > 8000:
                    # Still too large, take first and last parts
                    json_portion = json_portion[:4000] + "\n... [truncated] ...\n" + json_portion[-4000:]
                raw_response_text = f"Response summary (truncated from {len(raw_response_text)} chars):\n{json_portion}"
            else:
                # No JSON found, just truncate
                raw_response_text = raw_response_text[:5000] + "\n... [truncated] ...\n" + raw_response_text[-2000:]
        
        # Build context from previous sections
        context_parts = []
        
        # Add raw lab values if available (keep it concise)
        if labs_json:
            context_parts.append("RAW LAB VALUES:")
            context_parts.append(json.dumps(labs_json, indent=2))
        
        # Add raw vitals if available (keep it concise)
        if vitals_list:
            context_parts.append("RAW VITALS TIME-SERIES:")
            # Only include last 5 measurements for speed
            vitals_to_include = vitals_list[-5:] if len(vitals_list) > 5 else vitals_list
            context_parts.append(json.dumps(vitals_to_include, indent=2))
        
        # Add preprocessed summaries (these are already concise)
        if preprocessed_summaries:
            context_parts.append("PRE-PROCESSED DATA:")
            if preprocessed_summaries.get("tabular"):
                context_parts.append(f"Lab Analysis: {preprocessed_summaries['tabular']}")
            if preprocessed_summaries.get("timeseries"):
                context_parts.append(f"Vitals Trend: {preprocessed_summaries['timeseries']}")
        
        # Add tool logs (if any) - only last 3 for speed
        if tool_logs:
            relevant_logs = [log for log in tool_logs if "[ACTION]" in log or "[OBSERVATION]" in log]
            if relevant_logs:
                context_parts.append("TOOL EXECUTION RESULTS:")
                context_parts.append("\n".join(relevant_logs[-3:]))  # Last 3 relevant logs
        
        context_text = "\n\n".join(context_parts) if context_parts else "No additional context available."
        
        # OPTIMIZED Prompt - more direct and faster
        extraction_prompt = f"""You are a medical triage expert. Quickly extract the required information from the data below.

AGENT'S RESPONSE (may be truncated):
{raw_response_text[:3000] if len(raw_response_text) > 3000 else raw_response_text}

CLINICAL DATA:
{context_text}

Return ONLY a JSON object with these exact fields:
{{
  "differential_diagnosis": ["diagnosis1", "diagnosis2", "diagnosis3"],
  "triage_urgency": "RED" or "YELLOW" or "GREEN",
  "confidence_score": 0.0-1.0,
  "evidence_summary": "brief reasoning summary",
  "tool_verification_data": {{
    "sepsis_risk": {{
      "risk_score": <number>,
      "score_category": "High Risk" or "Low Risk"
    }}
  }}
}}

For risk_score: Analyze the lab values and vitals, then predict a clinically appropriate sepsis risk score (0-30). Use your medical knowledge.
Return ONLY valid JSON, no explanation.

Extract and return a JSON object with these fields:
1. "differential_diagnosis": Array of top 3-4 diagnosis names (strings). If you see "Unknown" or empty diagnoses, provide actual clinical diagnoses based on the response content.
2. "triage_urgency": One of "RED", "YELLOW", or "GREEN" based on the urgency level mentioned
3. "confidence_score": A number between 0.0 and 1.0 representing confidence
4. "evidence_summary": A concise summary of the cross-modal reasoning and evidence
5. "tool_verification_data": An object containing:
   - "sepsis_risk": Object with "risk_score" (number) and "score_category" ("High Risk" or "Low Risk")
   
CRITICAL: For the risk score, if it's not in the agent's response, you must calculate/predict it based on the available clinical data:
- Analyze the lab values (WBC, Lactate, Troponin, Hemoglobin, etc.)
- Analyze the vitals time-series data (SpO2, Heart Rate trends)
- Consider the patient notes and image analysis findings
- Based on clinical assessment, predict a sepsis risk score (a number, typically 0-30)
- Determine the category: "High Risk" if the score indicates significant concern, "Low Risk" otherwise
- Use your medical knowledge to assess the overall clinical picture and provide a clinically appropriate risk score

If any information is missing from the response, infer it from the context or use reasonable defaults.
Return ONLY valid JSON, no explanation text."""

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=extraction_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        # Extract JSON from response
        json_text = _get_raw_json_text(response)
        json_text = json_text.strip()
        
        # Remove markdown code blocks if present
        if json_text.startswith("```json"):
            json_text = json_text[7:].strip()
        elif json_text.startswith("```"):
            json_text = json_text[3:].strip()
        if json_text.endswith("```"):
            json_text = json_text[:-3].strip()
        
        # Find JSON object
        start_idx = json_text.find("{")
        end_idx = json_text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            json_text = json_text[start_idx:end_idx+1]
        
        extracted = json.loads(json_text)
        print(f"  ✅ Extracted outputs: {list(extracted.keys())}", file=sys.stderr)
        return extracted
        
    except Exception as e:  # noqa: BLE001
        import sys
        print(f"  ⚠️  Fallback extraction failed: {e}", file=sys.stderr)
        return None


def _generate_report_fast(
    user_input_text: str,
    uploaded_image_base64: str | None,
    uploaded_image_mime: str | None,
    labs_json: dict | None,
    vitals_list: list | None,
    image_analysis_text: str | None,
    preprocessed_summaries: dict,
) -> Tuple[Dict[str, Any] | None, str | None, List[str], List[str]]:
    """
    Fast path: Generate diagnostic report directly with Gemini using all available data.
    This skips the multi-turn agent loop for speed.
    
    Returns:
        Tuple of (report_dict, raw_json_text, tool_logs, errors)
    """
    client = get_gemini_client()
    tool_logs: List[str] = []
    errors: List[str] = []
    
    if client is None:
        errors.append("Gemini Client is not initialized.")
        return None, None, tool_logs, errors
    
    try:
        import sys
        print("  ⚡ Fast path: Generating report directly with Gemini...", file=sys.stderr)
        
        # Build comprehensive prompt with all data
        prompt_parts = []
        
        # Add patient notes
        if user_input_text:
            prompt_parts.append(f"PATIENT NOTES:\n{user_input_text}")
        
        # Add image analysis
        if image_analysis_text:
            prompt_parts.append(f"IMAGE ANALYSIS:\n{image_analysis_text}")
        
        # Add preprocessed summaries (already concise)
        if preprocessed_summaries.get("tabular"):
            prompt_parts.append(f"LAB ANALYSIS:\n{preprocessed_summaries['tabular']}")
        if preprocessed_summaries.get("timeseries"):
            prompt_parts.append(f"VITALS TREND:\n{preprocessed_summaries['timeseries']}")
        
        # Add raw data for risk score calculation
        if labs_json:
            prompt_parts.append(f"RAW LAB VALUES:\n{json.dumps(labs_json, indent=2)}")
        if vitals_list:
            # Only last 5 for speed
            vitals_to_include = vitals_list[-5:] if len(vitals_list) > 5 else vitals_list
            prompt_parts.append(f"RAW VITALS (last 5):\n{json.dumps(vitals_to_include, indent=2)}")
        
        full_prompt = "\n\n".join(prompt_parts)
        
        # Create multimodal content
        contents = []
        if uploaded_image_base64 and uploaded_image_mime:
            contents.append(file_to_part(uploaded_image_base64, uploaded_image_mime))
        contents.append(types.Part(text=f"""You are a senior medical triage expert. Analyze the following patient data and provide a comprehensive diagnostic report.

{full_prompt}

CRITICAL: Only use data that is explicitly provided above. Do NOT assume or infer lab values, vitals, or other clinical data that is not present. Focus your analysis on:
- Patient notes (if provided)
- Image analysis findings (if provided)
- Lab values that are explicitly listed (do not mention values not in the list)
- Vitals measurements that are explicitly listed (do not mention measurements not in the list)

Provide a JSON report with:
1. "differential_diagnosis": Array of 3-4 top diagnoses (strings) based ONLY on available data
2. "triage_urgency": "RED", "YELLOW", or "GREEN" based on available information
3. "confidence_score": Number 0.0-1.0 reflecting confidence given available data
4. "evidence_summary": Concise reasoning summary based ONLY on provided data
5. "tool_verification_data": {{
    "sepsis_risk": {{
        "risk_score": <number 0-30>,
        "score_category": "High Risk" or "Low Risk"
    }}
}}

For risk_score: Only use lab values and vitals that are explicitly provided. If lab values or vitals are not available, base the risk score on patient notes and image analysis findings only.

Return ONLY valid JSON, no explanation."""))
        
        # Call Gemini with JSON output config
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SENIOR_TRIAGE_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=DIAGNOSTIC_REPORT_SCHEMA,
            ),
        )
        
        # Extract and parse JSON
        raw_json_text = _get_raw_json_text(response)
        json_text = raw_json_text.strip()
        
        # Remove markdown if present
        if json_text.startswith("```json"):
            json_text = json_text[7:].strip()
        elif json_text.startswith("```"):
            json_text = json_text[3:].strip()
        if json_text.endswith("```"):
            json_text = json_text[:-3].strip()
        
        # Find JSON object
        start_idx = json_text.find("{")
        end_idx = json_text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            json_text = json_text[start_idx:end_idx+1]
        
        report = json.loads(json_text)
        tool_logs.append("[Fast Path] Report generated directly with Gemini.")
        print(f"  ✅ Fast path complete: {list(report.keys())}", file=sys.stderr)
        return report, json_text, tool_logs, errors
        
    except Exception as e:  # noqa: BLE001
        import sys
        errors.append(f"Fast path failed: {str(e)}")
        print(f"  ⚠️  Fast path failed: {e}", file=sys.stderr)
        # Fallback to regular extraction
        fallback_result = _extract_outputs_with_gemini(
            "",
            preprocessed_summaries,
            [],
            labs_json,
            vitals_list,
        )
        return fallback_result, None, tool_logs, errors