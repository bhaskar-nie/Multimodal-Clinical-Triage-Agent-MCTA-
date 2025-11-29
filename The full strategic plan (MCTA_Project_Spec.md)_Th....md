# **🏆 Multimodal Clinical Triage Agent (MCTA) Project Specification**

## **I. Project Overview and Strategic Justification**

**Project Goal:** To create a **Multimodal Clinical Triage Agent (MCTA)** that achieves a hackathon victory by demonstrating the maximum, innovative convergence of Gemini's cutting-edge capabilities, specifically targeting the **Medical Track**.

### **A. Core Requirements for Victory (Innovation Score Maximize)**

The project requires the simultaneous integration of the following three frontier features of the Gemini API:

1. **Maximized Multimodality:** Ingest and fuse data from four distinct modalities: **Text** (Notes), **Image** (Radiology), **Tabular** (Labs), and **Time-Series** (Vitals).  
2. **Deep Reasoning:** Use the **gemini-3-pro** model to execute multi-step clinical differential diagnosis and hypothesis testing (Deep Thinking).  
3. **Agentic Tool Use:** Ground the diagnosis using mandatory **Function Calling** to external, verifiable tools.

### **B. Function Calling Implementation (Required Tools)**

The agent **must** be able to autonomously decide when to call these functions:

| Function Name | Purpose | Input Parameters | Rationale |
| :---- | :---- | :---- | :---- |
| calculate\_sepsis\_risk | Computes a standardized clinical risk score (e.g., SOFA/APACHE II). | heart\_rate: int, blood\_pressure: int, lactate\_level: float, respiratory\_rate: int | Grounds the LMM's abstract diagnosis in algorithmic clinical data. |
| generate\_vitals\_visualization | Executes Matplotlib code to plot time-series vitals for graphical analysis. | time\_series\_data: JSON (containing SpO2, HR, timestamps) | Demonstrates autonomous code execution and subsequent multimodal analysis of the resulting image artifact. |

## **II. Technical Architecture Blueprint: Multimodal Data Pipeline**

The MCTA architecture follows a multi-step pipeline, substituting traditional AI stages with Gemini's native LMM capabilities.

### **A. Data Ingestion & Pre-processing (Host App Responsibility)**

**Crucial Note:** **No training or external dataset ingestion is required.** The model leverages its pre-trained knowledge. The host application must perform the following preparation steps:

1. **Text & Image:** Passed directly into the prompt payload.  
2. **Structured Data (Tabular & Time-Series):** **CRITICAL STEP:** Raw numerical data must be abstracted into high-level, contextually rich language features.  
   * **Tabular:** Convert raw lab numbers (e.g., WBC 18.5) into interpretive statements (e.g., "WBC count critically high").  
   * **Time-Series:** Convert raw sensor data into trend summaries (e.g., "SpO2 declined steadily over 6 hours").

### **B. Gemini API Function Checklist**

The implementation will rely on the following concepts and functions from the google-generativeai SDK.

| Feature | SDK Function / Class | Configuration Detail |
| :---- | :---- | :---- |
| **Model Selection** | model="gemini-3-pro" | Activates Deep Thinking and high reasoning fidelity. |
| **Configuration** | client.models.generate\_content | The core API call for generation. |
| **Multimodal Input** | contents: \[Part, Part, ...\] | Array structure to combine image, text, and structured language features. |
| **Agent Persona** | system\_instruction in GenerateContentConfig | Defines the "Senior Triage Specialist" persona and its reasoning rules. |
| **Tool Definition** | tools in GenerateContentConfig | Exposes the Python functions (calculate\_sepsis\_risk, etc.) to the LMM. |
| **Structured Output** | response\_mime\_type: "application/json" and response\_schema | Enforces the final Diagnostic Report JSON structure. |

## **III. 8-Hour Implementation Roadmap (Minute-by-Minute Execution Plan)**

The following plan uses Python and Streamlit, prioritizing the implementation of the complex Gemini features early on.

| Time Slot | Focus Area | Detailed Task for Cursor | Goal / Verification |
| :---- | :---- | :---- | :---- |
| **0:00 \- 1:00** | **Foundation & Shell** | 1\. Initialize Python/Streamlit project. Install google-generativeai, streamlit, matplotlib, python-dotenv. Create a basic Streamlit UI with file uploaders for a mock text note, an image, and a main chat input. | UI loads. Can upload files. |
| **1:00 \- 2:00** | **Core Multimodality** | 2\. Implement ingestion logic to read uploaded files into Part objects for the Gemini API call. Write a test call to gemini-3-pro that sends **both** an image and a text note simultaneously, asking for a diagnosis. | Successful multimodal response confirming both inputs were seen. |
| **2:00 \- 3:00** | **Structured Data Pre-proc** | 3\. Define mock data structures for Tabular (Labs) and Time-Series (Vitals). Write functions to convert this raw data into **interpretive Markdown/Text summaries**. Integrate these summaries as Part objects into the main prompt. | Prompt payload now contains four distinct modalities. |
| **3:00 \- 4:00** | **Agent Persona and Output Schema** | 4\. Define the rigorous **Senior Triage Specialist System Instruction**. Define the **DIAGNOSTIC\_REPORT\_SCHEMA** for JSON output. Integrate the system\_instruction and response\_schema into the GenerateContentConfig. | Agent responds using the clinical persona and outputs a parsable JSON object. |
| **4:00 \- 5:00** | **Function Calling: Risk Score** | 5\. Define the function **calculate\_sepsis\_risk** (with mock calculation logic). Expose this function via the tools parameter. Implement the logic to handle the multi-turn function calling pattern (executing the tool and feeding the result back to Gemini). | Agent autonomously calls the risk function and incorporates the score result into its reasoning. |
| **5:00 \- 6:00** | **Function Calling: Visualization** | 6\. Define **generate\_vitals\_visualization**. Use Matplotlib to plot mock time-series data, save to a byte buffer, and return the base64 encoded PNG string. Refine the agent prompt to ensure it requests this tool for trend confirmation. | Agent autonomously calls the visualization tool, and the host app displays the resulting base64 image. |
| **6:00 \- 7:00** | **Final UI Polish & Transparency** | 7\. Implement frontend logic to parse the final JSON report. Display the **Triage Urgency** using colored badges. Prominently display the **Tool Verification Results** (Risk Score, Visualization Chart). | The app looks submission-ready, professional, and visually appealing. |
| **7:00 \- 8:00** | **Documentation & Demo Prep** | 8\. Finalize error handling. Write a detailed README.md using this specification. **Final Action:** Script and record the 3-minute demo video. | All code is clean, documented, and the project is ready for submission. |

