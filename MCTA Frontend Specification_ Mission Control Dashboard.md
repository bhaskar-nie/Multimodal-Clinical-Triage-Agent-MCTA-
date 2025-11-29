# **MCTA Frontend Specification: Mission Control Dashboard**

This document details the required UI/UX for the MCTA application, designed as a modern, high-contrast single-page dashboard. The goal is clarity, speed, and transparency, ensuring all four input modalities and the agent's full reasoning trace are visible simultaneously. The application will be built using Python/Streamlit.

## **I. Design Principles and Aesthetics**

The design must project a high level of confidence, speed, and clinical authority.

| Attribute | Detail | Color / Value |
| :---- | :---- | :---- |
| **Theme** | High-Tech Clinical Dashboard | Professional, minimal. |
| **Primary Color (Accent)** | Teal 600 (Medical/Tech Focus) | \#0D9488 |
| **Critical Color (Alert)** | Red 600 (High Urgency) | \#DC2626 |
| **Warning Color** | Amber 500 (Medium Urgency) | \#F59E0B |
| **Success Color** | Green 600 (Low Urgency) | \#059669 |
| **Background** | Off-White / Light Gray | \#F9FAFB (Gray-50) |
| **Card Background** | Pure White, Rounded Corners | \#FFFFFF (Rounded-lg, Shadow-sm) |
| **Font** | Clean Sans-Serif (e.g., Inter) | High contrast text (\#1F2937) |
| **Layout** | Three fixed-width columns to prevent vertical scrolling during a single triage run. | Use of st.columns for layout structure. |

## **II. Application Structure (Three-Column Dashboard)**

The application is a single, non-scrolling dashboard divided into three main panels, visible at all times:

| Panel | Width Ratio (Approx.) | Content Role |
| :---- | :---- | :---- |
| **I. Input Panel** | 20% | Data Ingestion and Pre-processing Control. |
| **II. Reasoning Panel** | 50% | Agentic Chat Log, Function Call Trace, and Deep Thinking Visualization. |
| **III. Output Panel** | 30% | Final Diagnostic Synthesis, Triage Badge, and Quantitative Tool Results. |

## **III. Panel Component Detail**

### **I. Input Panel (Left Column)**

**Goal:** Collect or display all four patient data modalities.

| Component | Content Detail | Interaction/Styling | Modality |
| :---- | :---- | :---- | :---- |
| **Patient Context Card** | Title: **"Raw Modalities"** | White Card, Primary Teal Border. |  |
| **Text Input** | Large text area for patient/nurse notes (Text Modality). | Placeholder: "Enter Patient Symptoms and History..." | Text |
| **Image Uploader** | File uploader for X-ray/Scan images. | Accepts .jpg, .png. Display thumbnail after upload. | Image |
| **Structured Data Card** | Title: **"Data Abstraction"** | Displays the output of the host pre-processing script. |  |
| **Tabular Summary** | Read-only text area displaying the **language features** derived from raw labs. | Must be clearly labeled as "LABS FEATURE (Pre-processed)". | Tabular |
| **Time-Series Trend** | Read-only text area displaying the **language features** derived from vitals sensors. | Must be clearly labeled as "VITALS TREND (Pre-processed)". | Time-Series |
| **Run Button** | Button below inputs. | Large, Primary Teal button: **"Run Triage Agent"** | Trigger |

### **II. Reasoning Panel (Center Column)**

**Goal:** Transparency—show the agent's multi-step planning and tool orchestration.

| Component | Content Detail | Interaction/Styling |
| :---- | :---- | :---- |
| **System Status Header** | Sticky header above the chat area. | Dark Gray (\#1F2937), Light Teal text. Displays: \`MODEL: gemini-3-pro |
| **Chat Display Area** | Main vertical scrollable area. | Use Streamlit's native chat elements but customize for clarity. |
| **Agent Message (Persona)** | Use a clear **Nurse/Medical Icon** as the avatar. | **Teal** border or highlight. Displays the non-JSON reasoning text. |
| **Function Call Log (CRITICAL)** | Special message type to show agentic decision-making. | **Monospace font**, light gray background, labeled clearly as **"TOOL ACTION"** or **"OBSERVATION."** Use code blocks for tool payload/results. |
| **Chat Input Bar** | Input field for initial query or multi-turn follow-ups. | Standard bottom-aligned input. |

### **III. Output Panel (Right Column)**

**Goal:** Showcase the final, structured, and verifiable diagnosis—the core deliverable.

| Component | Content Detail | Interaction/Styling |
| :---- | :---- | :---- |
| **Triage Urgency Badge** | Displays the final Urgency value (RED, YELLOW, or GREEN) from the JSON output. | **Large, prominent banner/card** at the very top of the output panel. Use the corresponding alert color as the background. |
| **Diagnostic Synthesis Card** | Title: **"Final Diagnosis & Priority"** | Standard white card. Displays the differential diagnosis and confidence score from the JSON. |
| **Evidence Summary Card** | Title: **"Deep Thinking Trace (Explainability)"** | Lists supporting/conflicting evidence from all four modalities, as summarized by the agent. |
| **Tool Verification Card** | Title: **"Quantitative Grounding"** | Standard white card. Contains the results of the two function calls. |
| **Risk Score Display** | Displays the result of calculate\_sepsis\_risk. | If score is "High Risk," use **Burnt Orange** text (\#EA580C) and a strong border. |
| **Visualization Display** | Renders the base64 image generated by **generate\_vitals\_visualization**. | Use st.image to display the chart and ensure it fits responsively. |

## **IV. Frontend Constraints and Libraries**

1. **Libraries:** Python/Streamlit, Matplotlib (for visualization generation).  
2. **Visuals:** No custom CSS beyond what is easily implemented in Streamlit (e.g., Markdown/HTML with unsafe\_allow\_html=True for specific styling or badge creation).  
3. **Responsiveness:** Prioritize desktop three-column layout. Streamlit handles mobile stacking automatically.