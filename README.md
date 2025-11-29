# 🩺 Multimodal Clinical Triage Agent (MCTA)

**A Hackathon-Ready Demonstration of Gemini 2.5 Pro's Multimodality, Deep Reasoning, and Agentic Tool Use**

---

## 📋 Problem Statement

Emergency departments face critical challenges in rapid, accurate triage decisions. Traditional systems struggle to synthesize diverse data modalities (text notes, imaging, lab results, and time-series vitals) into actionable triage priorities. MCTA addresses this by leveraging **Gemini 2.5 Pro's advanced capabilities** to perform autonomous, tool-grounded clinical reasoning across four distinct data types.

---

## ✨ Key Features

### 1. **Four-Modality Fusion**
MCTA seamlessly integrates and reasons across:
- **Text Modality**: Patient/nurse notes (free-form clinical narrative)
- **Image Modality**: Radiology scans (X-rays, CT scans) via base64 encoding
- **Tabular Modality**: Lab results (WBC, Lactate, Troponin, Hemoglobin) pre-processed into interpretive summaries
- **Time-Series Modality**: Vitals trends (SpO2, Heart Rate) converted to high-level trend narratives

### 2. **Gemini 2.5 Pro Deep Thinking**
- Utilizes `gemini-2.5-pro` for multi-step differential diagnosis
- Structured JSON output enforced via `response_schema`
- Senior Triage Specialist persona with clinical reasoning protocols
- Transparent reasoning trace across all modalities

### 3. **Dual Function Calling (Agentic Tool Use)**
MCTA autonomously calls two Python tools to ground its reasoning:

- **`calculate_sepsis_risk`**: Computes quantitative sepsis risk score based on vitals and lab values
  - Inputs: Heart rate, blood pressure, lactate level, respiratory rate
  - Output: Risk score (integer) and category (High Risk / Low Risk)

- **`generate_vitals_visualization`**: Generates Matplotlib charts for visual trend confirmation
  - Input: Time-series vitals data (JSON string)
  - Output: Base64-encoded PNG image
  - Dual-axis plot: SpO2 (teal) and Heart Rate (orange)

### 4. **Mission Control Dashboard**
Professional, high-contrast UI with three-column layout:
- **Input Panel (20%)**: Data ingestion and pre-processing display
- **Reasoning Panel (50%)**: Multi-turn function call log with color-coded transparency
- **Output Panel (30%)**: Triage urgency badge, diagnostic synthesis, evidence summary, and tool verification

---

## 🔧 Gemini Integration

### Model Configuration
- **Model**: `gemini-2.5-pro` (via `google-genai` Python SDK)
- **System Instruction**: Senior Triage Specialist persona with clinical protocols
- **Structured Output**: Enforced JSON schema for diagnostic reports
- **Function Calling**: Multi-turn loop with autonomous tool invocation

### Technical Architecture
```
User Input
    ├─ Patient Notes (Text)
    └─ Medical Images
        ├─ X-ray/Scan Images (for visual analysis)
        ├─ Lab Report Images (for data extraction)
        └─ Vitals Chart Images (for data extraction)
    ↓
Automatic Data Extraction (Gemini 2.5 Pro)
    ├─ Extract Lab Values from Lab Report Images
    │   └─ WBC, Lactate, Troponin, Hemoglobin
    └─ Extract Vitals from Vitals Chart Images
        └─ Time-series: SpO2, Heart Rate
    ↓
Pre-processing Layer
    ├─ Tabular Data → Interpretive Summary
    └─ Time-Series Data → Trend Narrative
    ↓
Gemini 2.5 Pro (Multimodal Input)
    ├─ Text Part (Patient Notes)
    ├─ Image Part (X-ray/Scan - base64)
    ├─ Tabular Summary Part (from extracted labs)
    └─ Time-Series Summary Part (from extracted vitals)
    ↓
Multi-Turn Function Calling Loop
    ├─ Turn 1: Model requests tools
    ├─ Host executes: calculate_sepsis_risk, generate_vitals_visualization
    └─ Turn 2: Model synthesizes final JSON report
    ↓
Structured Diagnostic Report
    ├─ Differential Diagnosis (array)
    ├─ Triage Urgency (RED/YELLOW/GREEN)
    ├─ Confidence Score (0.0-1.0)
    ├─ Evidence Summary (cross-modal reasoning)
    └─ Tool Verification Data (risk score + visualization base64)
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11 (recommended)
- Conda (recommended for environment management)
- Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### Step 1: Clone or Download the Project
```bash
# Navigate to project directory
cd "Multimodal Clinical Triage Agent (MCTA)"
```

### Step 2: Create Conda Environment
```bash
conda create -n mcta-env python=3.11 -y
conda activate mcta-env
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Gemini API Key

Create a `.env` file in the project root:

```bash
echo GEMINI_API_KEY="YOUR_API_KEY_HERE" > .env
```

Or manually create `.env`:
```
GEMINI_API_KEY=your_actual_api_key_here
```

**Note**: The project uses the `google-genai` client which automatically reads `GEMINI_API_KEY` from the environment.

---

## 🏃 Running the Application

### Start the Streamlit Dashboard
```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

### Using the Dashboard

1. **Input Panel**
   - **Enter Patient Notes** (required): Type patient symptoms, history, and clinical observations
   - **Upload Medical Images** (optional, multiple files supported):
     - **X-ray/Scan Images**: Upload radiology images (chest X-rays, CT scans, etc.) for visual analysis
     - **Lab Reports**: Upload images of lab reports - Gemini will automatically extract lab values (WBC, Lactate, Troponin, Hemoglobin)
     - **Vitals Charts**: Upload images of vitals charts - Gemini will automatically extract time-series vitals data (SpO2, Heart Rate)
   - Click **"Run Triage Agent"** - Data extraction from images happens automatically!
   
   **How it works:**
   - When you click "Run Triage Agent", the system automatically:
     1. Extracts lab values and vitals from uploaded lab report/vitals chart images using Gemini 2.5 Pro
     2. Uses the extracted data along with patient notes and X-ray/scan images
     3. Generates a comprehensive diagnostic report
   - No manual data entry required - everything is extracted from images automatically!

2. **Reasoning Panel (Center Column)**
   - View system status (`MODEL: gemini-2.5-pro`)
   - Monitor chat history
   - Track function call log:
     - `[ACTION]` entries (Amber) = Model requests tools
     - `[OBSERVATION]` entries (Teal) = Tool execution results
     - `[ERROR]` entries (Red) = Execution failures

3. **Output Panel (Right Column)**
   - **Triage Urgency Badge**: Large, color-coded (RED/YELLOW/GREEN)
   - **Final Diagnosis & Priority**: Top 3 differential diagnoses with confidence score
   - **Deep Thinking Trace**: Expandable evidence summary
   - **Quantitative Grounding**:
     - Sepsis risk score (color-coded: Orange for High Risk, Teal for Low Risk)
     - Vitals visualization chart (when generated)

---

## 🧪 Testing & Verification

### Standalone Agent Verification

Run the verification script to test the multi-turn logic outside of Streamlit:

```bash
python verify_agent.py
```

This script:
- Tests the complete multi-turn function calling pipeline
- Uses hardcoded high-risk scenario data
- Prints tool logs and final JSON output to console
- Verifies that both tools are called correctly

### Expected Output
```
[Turn 1] Model requested 2 function call(s).
[ACTION] Model requested: calculate_sepsis_risk({'heart_rate': 120, ...})
[OBSERVATION] Host executed calculate_sepsis_risk: {'risk_score': 19, ...}
[ACTION] Model requested: generate_vitals_visualization({'time_series_data': '...'})
[OBSERVATION] Host executed generate_vitals_visualization: 'base64_encoded_png...'
[Turn 2] Final response received (no function calls).

Final Diagnostic Report:
{
  "differential_diagnosis": [...],
  "triage_urgency": "RED",
  "confidence_score": 0.85,
  ...
}
```

---

## 📁 Project Structure

```
MCTA/
├── app.py                    # Main Streamlit application (UI)
├── config.py                 # Gemini model config, schema, system instruction
├── tools.py                  # Function calling tools (sepsis risk, visualization)
├── utils.py                  # Multimodal content building, agent orchestration
├── data_processor.py         # Data abstraction layer (labs/vitals → summaries)
├── ui_components.py          # Reusable UI components (badges, cards, tool logs)
├── mock_data.py              # Mock lab and vitals data for demo
├── verify_agent.py            # Standalone verification script
├── requirements.txt           # Python dependencies
├── README.md                  # This file
└── .env                       # API key configuration (create this)
```

### Key Files Explained

- **`app.py`**: Three-column Streamlit dashboard, input validation, UI rendering
- **`config.py`**: `DIAGNOSTIC_REPORT_SCHEMA`, `SENIOR_TRIAGE_SYSTEM_INSTRUCTION`, client initialization
- **`tools.py`**: `calculate_sepsis_risk()`, `generate_vitals_visualization()`, `TOOL_CONFIG`
- **`utils.py`**: `build_patient_contents()`, `run_triage_agent()` (multi-turn loop), JSON parsing
- **`data_processor.py`**: `preprocess_tabular_data()`, `preprocess_timeseries_data()`
- **`ui_components.py`**: `render_triage_badge()`, `render_card()`, `render_tool_action()`, `STATUS_COLORS`

---

## 🔒 Safety & Disclaimers

**⚠️ CRITICAL WARNING**

This project is a **technical demonstration only** and **MUST NOT** be used for:
- Real clinical decision-making
- Patient care or diagnosis
- Medical triage in production environments

**Key Limitations:**
- The sepsis risk calculation is **heavily simplified** and not validated
- No external medical datasets or model training (uses in-context learning only)
- Outputs are **non-diagnostic** and for hackathon/research purposes only
- Always clearly state in demos that this is a proof-of-concept

---

## 🎯 Conclusion

MCTA successfully demonstrates:

✅ **Maximized Multimodality**: Four distinct data types (Text, Image, Tabular, Time-Series)  
✅ **Deep Reasoning**: Gemini 2.5 Pro's multi-step differential diagnosis  
✅ **Agentic Tool Use**: Autonomous function calling with quantitative grounding  
✅ **Transparency**: Full reasoning trace and tool verification  
✅ **Production-Ready UI**: Professional dashboard with color-coded urgency indicators  

**This project proves that advanced LLMs can act as intelligent clinical assistants when properly configured with structured outputs, function calling, and multimodal input pipelines.**

---

## 📚 Additional Resources

- [Gemini API Documentation](https://ai.google.dev/docs)
- [Google Generative AI Python SDK](https://github.com/google/generative-ai-python)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

## 👥 Credits

Built for the **Medical Track** hackathon, showcasing Gemini 2.5 Pro's capabilities in clinical reasoning and multimodal AI.

**Version**: 1.0.0  
**Last Updated**: 2025  
**License**: Hackathon Project (Educational/Demonstration Only)
