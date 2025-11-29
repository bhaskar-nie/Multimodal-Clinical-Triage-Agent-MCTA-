import base64
import html
import json
import os

import streamlit as st
from dotenv import load_dotenv

from mock_data import get_default_data, get_mock_data
from ui_components import (
    render_card,
    render_system_status,
    render_tool_action,
    render_triage_badge,
)
from utils import (
    extract_data_from_image,
    preprocess_tabular_data,
    preprocess_timeseries_data,
    run_triage_agent,
    _extract_outputs_with_gemini,
    _generate_report_fast,
)


load_dotenv()

st.set_page_config(
    page_title="MCTA · Multimodal Clinical Triage Agent",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    body {
        background-color: #F9FAFB;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []

if "diagnostic_report" not in st.session_state:
    st.session_state.diagnostic_report = None

if "vitals_image_base64" not in st.session_state:
    st.session_state.vitals_image_base64 = None

if "raw_json_response" not in st.session_state:
    st.session_state.raw_json_response = None

# Initialize patient data with default healthy values
if "patient_labs" not in st.session_state:
    default_data = get_default_data()
    st.session_state.patient_labs = default_data["labs"]

if "patient_vitals" not in st.session_state:
    default_data = get_default_data()
    st.session_state.patient_vitals = default_data["vitals"]


def encode_uploaded_image(file) -> tuple[str, str] | None:
    """
    Encode Streamlit uploaded file to base64 and detect MIME type.
    
    Returns:
        Tuple of (base64_string, mime_type) or None if no file.
    """
    if file is None:
        return None
    
    # Detect MIME type from file extension/type
    file_type = file.type.lower() if hasattr(file, "type") else ""
    if "jpeg" in file_type or "jpg" in file_type:
        mime_type = "image/jpeg"
    elif "png" in file_type:
        mime_type = "image/png"
    else:
        # Fallback: try to infer from filename
        name_lower = file.name.lower() if hasattr(file, "name") else ""
        if name_lower.endswith((".jpg", ".jpeg")):
            mime_type = "image/jpeg"
        elif name_lower.endswith(".png"):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"  # Default fallback
    
    # Read file bytes and encode to base64
    file.seek(0)  # Reset file pointer
    data = file.read()
    base64_data = base64.b64encode(data).decode("utf-8")
    
    return (base64_data, mime_type)


def main():
    st.title("🩺 Multimodal Clinical Triage Agent (MCTA)")
    api_key_present = bool(os.getenv("GEMINI_API_KEY"))
    if not api_key_present:
        st.warning(
            "GEMINI_API_KEY is not configured. Set it in a .env file or your environment "
            "to enable live triage calls.",
            icon="⚠️",
        )

    # HORIZONTAL LAYOUT: Sections arranged in rows instead of columns
    
    # SECTION 1: INPUT PANEL (Full Width)
    st.markdown("### 🧵 Patient Data Input")
    st.markdown("---")
    
    # Simplified single-column layout: Patient Notes + Image Uploads
    st.markdown("#### 📝 Patient Notes")
    notes = st.text_area(
        "Patient / Nurse Notes",
        placeholder="Enter Patient Symptoms and History...",
        height=150,
        key="patient_notes",
        label_visibility="collapsed",
    )
    
    st.markdown("---")
    st.markdown("#### 🖼️ Medical Images Upload")
    st.caption("Upload X-ray/scan images, lab reports, or vitals charts. Data will be automatically extracted using Gemini 2.5 Pro.")
    
    # Single file uploader that accepts multiple image types
    uploaded_images = st.file_uploader(
        "Upload Medical Images (X-ray/Scan, Lab Report, or Vitals Chart)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="medical_images_uploader",
        label_visibility="collapsed",
    )
    
    # Display uploaded images
    if uploaded_images:
        st.markdown("**Uploaded Images:**")
        image_cols = st.columns(min(len(uploaded_images), 3))
        for idx, img in enumerate(uploaded_images):
            with image_cols[idx % 3]:
                st.image(img, caption=img.name)
    
    # Info message
    st.info(
        "💡 **How it works**: Upload images of X-rays/scans, lab reports, or vitals charts. "
        "Gemini 2.5 Pro will automatically extract lab values and vitals data from these images "
        "when you run the triage agent. No manual data entry required!",
        icon="ℹ️",
    )
    
    # Pre-processing summaries - Only show after agent runs
    # Store pre-processed summaries in session state after agent execution
    if "preprocessed_summaries" not in st.session_state:
        st.session_state.preprocessed_summaries = None
    
    # Run button
    run_clicked = st.button(
        "🚀 Run Triage Agent",
        type="primary",
        use_container_width=True,
    )
    
    if run_clicked:
        if not api_key_present:
            st.error(
                "Cannot run triage without GEMINI_API_KEY configured.",
                icon="⛔",
            )
        elif not notes:
            st.error(
                "Please enter patient notes to provide sufficient clinical context.",
                icon="📝",
            )
        else:
            # Validate and process uploaded images
            xray_image = None
            xray_b64 = None
            xray_mime = None
            
            # Separate images: X-ray/scan vs lab/vitals reports
            lab_vitals_images = []
            
            if uploaded_images:
                for img in uploaded_images:
                    file_type = img.type.lower() if hasattr(img, "type") else ""
                    file_name = img.name.lower() if hasattr(img, "name") else ""
                    
                    # Check for valid image types
                    valid_types = ["image/jpeg", "image/jpg", "image/png"]
                    valid_extensions = [".jpg", ".jpeg", ".png"]
                    
                    is_valid_type = any(vt in file_type for vt in valid_types)
                    is_valid_extension = any(ve in file_name for ve in valid_extensions)
                    
                    if not (is_valid_type or is_valid_extension):
                        st.warning(
                            f"⚠️ Invalid image file type for {img.name}. Skipping.",
                            icon="⚠️",
                        )
                        continue
                    
                    # Heuristic: Check filename/type to determine if it's X-ray/scan or lab/vitals
                    # X-ray/scan keywords: xray, x-ray, scan, ct, mri, radiology
                    # Lab/vitals keywords: lab, report, vitals, chart, blood
                    name_lower = file_name
                    if any(keyword in name_lower for keyword in ["xray", "x-ray", "scan", "ct", "mri", "radiology", "chest", "lung"]):
                        # This is likely an X-ray/scan image
                        if xray_image is None:  # Use first X-ray/scan found
                            xray_image = img
                            img_data = encode_uploaded_image(img)
                            if img_data:
                                xray_b64, xray_mime = img_data
                    else:
                        # This is likely a lab report or vitals chart
                        lab_vitals_images.append(img)
            
            # Initialize image analyses list
            all_image_analyses = []
            
            # Analyze X-ray/scan images with Gemini
            if xray_image and api_key_present:
                with st.spinner("Analyzing X-ray/scan image with Gemini 2.5 Pro..."):
                    import sys
                    print(f"📸 Analyzing X-ray/scan image: {xray_image.name}", file=sys.stderr)
                    _, _, xray_analysis, _ = extract_data_from_image(xray_b64, xray_mime)
                    if xray_analysis:
                        all_image_analyses.append(xray_analysis)
                        print(f"  ✅ X-ray analysis complete ({len(xray_analysis)} chars)", file=sys.stderr)
            
            # Extract data from lab/vitals images automatically
            if lab_vitals_images and api_key_present:
                with st.spinner("Extracting lab values and vitals from images using Gemini 2.5 Pro..."):
                    import sys
                    print(f"📸 Processing {len(lab_vitals_images)} image(s) for data extraction...", file=sys.stderr)
                    
                    for img in lab_vitals_images:
                        print(f"  📄 Analyzing: {img.name}", file=sys.stderr)
                        img_data = encode_uploaded_image(img)
                        if img_data:
                            img_b64, img_mime = img_data
                            
                            # Extract data and get Gemini's analysis
                            extracted_labs, extracted_vitals, image_analysis, extraction_errors = extract_data_from_image(
                                img_b64, img_mime
                            )
                            
                            # Store image analysis for later use
                            if image_analysis:
                                all_image_analyses.append(image_analysis)
                            
                            if extraction_errors:
                                for err in extraction_errors:
                                    st.warning(f"⚠️ Extraction warning for {img.name}: {err}")
                                    print(f"  ⚠️  {err}", file=sys.stderr)
                            
                            # Update session state with extracted data
                            if extracted_labs:
                                print(f"  ✅ Successfully extracted lab values: {extracted_labs}", file=sys.stderr)
                                for key, value in extracted_labs.items():
                                    if value is not None:
                                        st.session_state.patient_labs[key] = value
                                st.success(f"✅ Extracted lab values from {img.name}")
                            else:
                                print(f"  ℹ️  No lab values found in {img.name}", file=sys.stderr)
                            
                            if extracted_vitals:
                                print(f"  ✅ Successfully extracted {len(extracted_vitals)} vitals measurements", file=sys.stderr)
                                # Replace vitals with extracted data (don't merge with defaults)
                                st.session_state.patient_vitals = extracted_vitals
                                st.success(f"✅ Extracted {len(extracted_vitals)} vitals measurements from {img.name}")
                            else:
                                print(f"  ℹ️  No vitals data found in {img.name}", file=sys.stderr)
                        else:
                            st.warning(f"⚠️ Could not encode image: {img.name}")
                            print(f"  ❌ Failed to encode image: {img.name}", file=sys.stderr)
            
            # Proceed with execution
            st.session_state.chat_history = []
            st.session_state.tool_logs = []
            st.session_state.diagnostic_report = None
            st.session_state.vitals_image_base64 = None
            st.session_state.raw_json_response = None

            st.session_state.chat_history.append(
                {"role": "user", "content": notes}
            )

            # Use ONLY extracted data from images - no defaults
            # Only use labs/vitals if they were actually extracted from images
            labs_json = st.session_state.patient_labs if st.session_state.patient_labs else None
            vitals_list = st.session_state.patient_vitals if st.session_state.patient_vitals else None
            
            # Pre-process data ONLY if we have actual data (not empty dicts/lists)
            try:
                if labs_json and isinstance(labs_json, dict) and any(v is not None and v != 0 for v in labs_json.values()):
                    tabular_summary = preprocess_tabular_data(labs_json)
                else:
                    tabular_summary = "Tabular Data Feature: No lab data extracted from images."
            except Exception as e:
                tabular_summary = f"Tabular Data Feature: Error processing lab data: {e}"
            
            try:
                if vitals_list and isinstance(vitals_list, list) and len(vitals_list) > 0:
                    timeseries_summary = preprocess_timeseries_data(vitals_list)
                else:
                    timeseries_summary = "Time-Series Feature: No vitals data extracted from images."
            except Exception as e:
                timeseries_summary = f"Time-Series Feature: Error processing vitals data: {e}"
            st.session_state.preprocessed_summaries = {
                "tabular": tabular_summary,
                "timeseries": timeseries_summary,
            }

            # Status indicator
            status_placeholder = st.empty()
            status_placeholder.info("🔍 **Status: Examining patient data...**")
            
            with st.spinner("Running MCTA triage agent..."):
                import sys
                print("\n" + "="*60, file=sys.stderr)
                print("MCTA: Starting triage analysis...", file=sys.stderr)
                print("="*60, file=sys.stderr)
                
                status_placeholder.info("🔍 **Status: Analyzing multimodal inputs...**")
                print("📊 Step 1: Processing patient notes and images...", file=sys.stderr)
                
                # Combine all image analyses into a single text
                combined_image_analysis = None
                if all_image_analyses:
                    combined_image_analysis = "\n\n".join(all_image_analyses)
                    print(f"📄 Combined image analysis ({len(combined_image_analysis)} chars) will be included in prompt", file=sys.stderr)
                
                # OPTIMIZATION: Use fast path for speed (direct Gemini call)
                import time
                start_time = time.time()
                print("⚡ Using fast Gemini extraction path for speed...", file=sys.stderr)
                status_placeholder.info("⚡ **Status: Fast analysis mode...**")
                
                report, raw_json_text, tool_logs, errors = _generate_report_fast(
                    notes,
                    xray_b64,
                    xray_mime,
                    labs_json,
                    vitals_list,
                    combined_image_analysis,
                    st.session_state.get("preprocessed_summaries", {}),
                )
                
                elapsed = time.time() - start_time
                print(f"⏱️  Total processing time: {elapsed:.2f}s", file=sys.stderr)
                
                status_placeholder.info("✅ **Status: Analysis complete!**")
                print("\n" + "="*60, file=sys.stderr)
                print("✅ MCTA: Triage analysis completed successfully!", file=sys.stderr)
                if report:
                    print(f"📋 Triage Urgency: {report.get('triage_urgency', 'N/A')}", file=sys.stderr)
                    print(f"📊 Confidence Score: {report.get('confidence_score', 0)*100:.1f}%", file=sys.stderr)
                print("="*60 + "\n", file=sys.stderr)

            st.session_state.tool_logs = tool_logs
            st.session_state.raw_json_response = raw_json_text

            # Debug: Print report status and try to recover if report is None
            import sys
            if report:
                print(f"✅ Report received: {type(report)}, keys: {list(report.keys()) if isinstance(report, dict) else 'N/A'}", file=sys.stderr)
                st.session_state.diagnostic_report = report
            else:
                print(f"❌ No report received. raw_json_text length: {len(raw_json_text) if raw_json_text else 0}", file=sys.stderr)
                print(f"   Errors: {errors}", file=sys.stderr)
                # Try to create a report from raw_json_text if available
                if raw_json_text:
                    try:
                        import json
                        # Try to parse the raw JSON
                        parsed = json.loads(raw_json_text)
                        if isinstance(parsed, dict):
                            st.session_state.diagnostic_report = parsed
                            print(f"✅ Successfully parsed raw_json_text into report", file=sys.stderr)
                    except Exception as e:
                        print(f"⚠️  Could not parse raw_json_text: {e}", file=sys.stderr)
            
            # Fallback: If report is still None or incomplete, use Gemini to extract information
            # Also check if risk score is missing
            report = st.session_state.diagnostic_report or {}
            tool_data = report.get("tool_verification_data") or {}
            has_risk_score = False
            if isinstance(tool_data, dict):
                has_risk_score = (
                    tool_data.get("sepsis_risk") is not None or
                    tool_data.get("risk_score") is not None or
                    tool_data.get("calculate_sepsis_risk") is not None
                )
            
            if not st.session_state.diagnostic_report or not st.session_state.diagnostic_report.get("differential_diagnosis") or not has_risk_score:
                print("🔄 Using Gemini fallback to extract diagnosis, reasoning, and risk score...", file=sys.stderr)
                fallback_results = _extract_outputs_with_gemini(
                    raw_json_text or "",
                    st.session_state.get("preprocessed_summaries", {}),
                    tool_logs,
                    st.session_state.get("patient_labs", {}),
                    st.session_state.get("patient_vitals", []),
                )
                if fallback_results:
                    # Merge fallback results into diagnostic report
                    if not st.session_state.diagnostic_report:
                        st.session_state.diagnostic_report = {}
                    # Deep merge tool_verification_data if it exists
                    if "tool_verification_data" in fallback_results and "tool_verification_data" in st.session_state.diagnostic_report:
                        existing_tvd = st.session_state.diagnostic_report["tool_verification_data"] or {}
                        new_tvd = fallback_results["tool_verification_data"] or {}
                        st.session_state.diagnostic_report["tool_verification_data"] = {**existing_tvd, **new_tvd}
                        # Remove tool_verification_data from fallback_results before update
                        fallback_results_without_tvd = {k: v for k, v in fallback_results.items() if k != "tool_verification_data"}
                        st.session_state.diagnostic_report.update(fallback_results_without_tvd)
                    else:
                        st.session_state.diagnostic_report.update(fallback_results)
                    print(f"✅ Fallback extraction complete: {list(fallback_results.keys())}", file=sys.stderr)
            
            # Try to pull visualization from tool_verification_data if present
            # Only do this if we have a report
            if st.session_state.diagnostic_report:
                report_for_viz = st.session_state.diagnostic_report
                # The model may store it under various keys (visualization_base64, base64_image, etc.)
                tvd = report_for_viz.get("tool_verification_data") or {}
                
                # Try multiple extraction paths
                vis_candidates = [
                    tvd.get("visualization_base64"),
                    tvd.get("base64_image"),
                    tvd.get("vitals_visualization"),
                ]
                
                # Check generate_vitals_visualization result
                gen_viz = tvd.get("generate_vitals_visualization")
                if isinstance(gen_viz, dict):
                    vis_candidates.append(gen_viz.get("result"))
                elif isinstance(gen_viz, str):
                    vis_candidates.append(gen_viz)
                
                # Find first valid string (not dict)
                visualization_base64 = None
                for candidate in vis_candidates:
                    if candidate and isinstance(candidate, str):
                        visualization_base64 = candidate
                        break
                
                st.session_state.vitals_image_base64 = visualization_base64
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": "Diagnostic report generated successfully.",
                    }
                )
            else:
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": "I was unable to generate a diagnostic report.",
                    }
                )

            for err in errors:
                st.error(err)
    
    # Display pre-processed summaries only after agent has run (not with default values)
    if st.session_state.get("preprocessed_summaries"):
        st.markdown("---")
        st.markdown("### 🔄 Data Abstraction (Pre-processing)")
        col_pre1, col_pre2 = st.columns(2)
        
        with col_pre1:
            st.text_area(
                "LABS FEATURE (Pre-processed)",
                value=st.session_state.preprocessed_summaries["tabular"],
                height=120,
                disabled=True,
                key="tabular_summary_display",
            )
        
        with col_pre2:
            st.text_area(
                "VITALS TREND (Pre-processed)",
                value=st.session_state.preprocessed_summaries["timeseries"],
                height=120,
                disabled=True,
                key="timeseries_summary_display",
            )
    
    st.markdown("---")
    
    # SECTION 2: REASONING PANEL (Full Width)
    st.markdown("### 🧠 Reasoning & Tool Trace")
    render_system_status()
    
    # Reasoning content - Chat History only (Function Call Log removed)
    st.markdown("#### 💬 Chat History")
    reasoning_container = st.container()
    with reasoning_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div style="
                        text-align: right;
                        background-color: #E5E7EB;
                        padding: 0.5rem 0.75rem;
                        border-radius: 0.5rem;
                        margin-bottom: 0.3rem;
                        display: inline-block;
                        max-width: 100%;
                        color: #1F2937;
                    ">
                        {msg["content"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="
                        text-align: left;
                        background-color: #ECFEFF;
                        border-left: 4px solid #0D9488;
                        padding: 0.5rem 0.75rem;
                        border-radius: 0.5rem;
                        margin-bottom: 0.3rem;
                        max-width: 100%;
                        color: #1F2937;
                    ">
                        🧑‍⚕️ {msg["content"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    
    st.markdown("---")
    
    # SECTION 3: OUTPUT PANEL (Full Width)
    st.markdown("### 📊 Output & Verification")
    # Output content in horizontal layout
    col_output1, col_output2, col_output3 = st.columns([1, 1, 1])
    
    triage_urgency = None
    if st.session_state.diagnostic_report:
        triage_urgency = st.session_state.diagnostic_report.get("triage_urgency")
    
    report = st.session_state.diagnostic_report or {}
    
    with col_output1:
        render_triage_badge(triage_urgency)
        
        # Hide raw JSON in an expander (optional, for debugging)
        if st.session_state.raw_json_response:
            with st.expander("🔍 Raw JSON (Debug)", expanded=False):
                st.code(
                    st.session_state.raw_json_response,
                    language="json",
                )
    
    with col_output2:
        # Diagnostic synthesis - Use Streamlit components instead of raw HTML for better rendering
        diff = report.get("differential_diagnosis") or []
        confidence = report.get("confidence_score")

        st.markdown(
            """
            <div style="
                background-color: #FFFFFF;
                border-radius: 0.75rem;
                padding: 1rem 1.25rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                margin-bottom: 0.75rem;
                border: 1px solid #E5E7EB;
            ">
                <div style="font-weight: 600; margin-bottom: 0.75rem; color: #0F172A; font-size: 1rem;">
                    📌 Final Diagnosis & Priority
                </div>
            """,
            unsafe_allow_html=True,
        )
        
        if diff:
            st.markdown("**Top Differential Diagnoses:**")
            
            for idx, d in enumerate(diff, start=1):
                # Handle both string and dict formats
                if isinstance(d, dict):
                    # Try multiple keys to find diagnosis name
                    diagnosis = (
                        d.get("diagnosis") or 
                        d.get("name") or 
                        d.get("condition") or 
                        d.get("disease") or
                        None
                    )
                    # If still not found, try to construct from dict keys
                    if not diagnosis or diagnosis == "Unknown" or diagnosis == "{}":
                        # Extract meaningful keys (skip reasoning/evidence keys)
                        skip_keys = {"reasoning", "reason", "evidence", "confidence", "probability"}
                        meaningful = {k: v for k, v in d.items() if k not in skip_keys and v}
                        if meaningful:
                            diagnosis = ", ".join([f"{k}: {v}" for k, v in meaningful.items()])
                        else:
                            diagnosis = "Diagnosis details unavailable"
                    reasoning = d.get("reasoning", d.get("reason", ""))
                    
                    # Use Streamlit container for each diagnosis card
                    # Escape HTML in diagnosis and reasoning to prevent raw HTML display
                    diagnosis_escaped = html.escape(str(diagnosis)) if diagnosis else "Unknown"
                    reasoning_escaped = html.escape(str(reasoning)) if reasoning else ""
                    
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #F9FAFB;
                                padding: 0.75rem;
                                border-radius: 0.5rem;
                                border-left: 3px solid #0D9488;
                                margin-bottom: 0.75rem;
                            ">
                                <div style="font-weight: 600; color: #0F172A; margin-bottom: 0.4rem;">
                                    {idx}. {diagnosis_escaped}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if reasoning_escaped:
                            st.markdown(
                                f"""
                                <div style="
                                    color: #4B5563;
                                    font-size: 0.9rem;
                                    line-height: 1.5;
                                    margin-left: 0.5rem;
                                    margin-bottom: 0.75rem;
                                ">
                                    {reasoning_escaped}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                elif isinstance(d, str):
                    # Escape HTML in string diagnosis
                    d_escaped = html.escape(d)
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #F9FAFB;
                            padding: 0.75rem;
                            border-radius: 0.5rem;
                            border-left: 3px solid #0D9488;
                            margin-bottom: 0.75rem;
                        ">
                            <div style="font-weight: 600; color: #0F172A;">
                                {idx}. {d_escaped}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown("<div style='color: #6B7280;'>No diagnosis available yet.</div>", unsafe_allow_html=True)
        
        if confidence is not None:
            # Format confidence as percentage with color coding
            confidence_pct = confidence * 100
            if confidence_pct >= 80:
                conf_color = "#059669"  # Green
            elif confidence_pct >= 60:
                conf_color = "#F59E0B"  # Amber
            else:
                conf_color = "#DC2626"  # Red
            
            st.markdown("---")
            st.markdown(
                f"""
                <div style="margin-top: 0.5rem;">
                    <strong style='color: #0F172A;'>Confidence Score:</strong> 
                    <span style='color: {conf_color}; font-weight: 600; font-size: 1.1em;'>{confidence_pct:.1f}%</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Evidence summary - Enhanced with expander for cleaner presentation
        evidence_summary = report.get("evidence_summary") or ""
        
        # Also try to extract reasoning from differential_diagnosis if evidence_summary is empty
        if not evidence_summary and diff:
            # Combine reasoning from all diagnoses
            reasoning_parts = []
            for d in diff:
                if isinstance(d, dict):
                    reasoning = d.get("reasoning", d.get("reason", ""))
                    if reasoning:
                        reasoning_parts.append(reasoning)
            if reasoning_parts:
                evidence_summary = " ".join(reasoning_parts)
        
        with st.expander("🧬 Deep Thinking Trace (Explainability)", expanded=True):
            if evidence_summary:
                # Escape HTML in evidence summary to prevent raw HTML display
                evidence_escaped = html.escape(str(evidence_summary))
                st.markdown(
                    f"""
                    <div style="
                        background-color: #F9FAFB;
                        padding: 1rem;
                        border-radius: 0.5rem;
                        border-left: 4px solid #0D9488;
                        font-size: 0.9rem;
                        line-height: 1.6;
                        color: #1F2937;
                    ">
                        {evidence_escaped}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("The agent's cross-modal reasoning trace will appear here once a diagnosis is generated.")
    
    with col_output3:
        # Output column 3 - currently empty (risk score card removed)
        pass



if __name__ == "__main__":
    main()



