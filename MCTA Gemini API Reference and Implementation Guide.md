# **MCTA Gemini API Reference and Implementation Guide**

This guide is the complete technical reference for the MCTA project, focusing exclusively on the specific functions required from the google-generativeai Python SDK to implement the architecture defined in the main project specification.

## **I. Data Requirement: Training and Datasets**

**CRITICAL ANSWER:** **NO EXTERNAL DATASETS OR MODEL TRAINING ARE REQUIRED.**

The MCTA uses the advanced, pre-trained knowledge of gemini-3-pro through **In-Context Learning (ICL)** and **Tool Grounding**. All clinical protocols and risk score logic are provided to the model in two ways:

1. **System Instructions:** Defining the agent's behavior and clinical rules.  
2. **Function Calling:** Providing access to external, verifiable Python functions that execute quantitative logic (risk scores, visualization).

## **II. Required Imports and Initialization**

The following imports and initialization steps are mandatory for the Python environment.

import os  
import json  
import base64  
from google import genai  
from google.genai import types \# Essential for all structured and configuration objects  
from google.genai.errors import APIError   
import matplotlib.pyplot as plt \# Required for generate\_vitals\_visualization tool  
import io \# Required for Matplotlib output handling

\# Client Initialization  
client \= genai.Client()  
\# Model Selection  
MODEL\_NAME \= "gemini-3-pro" 

## **III. Core API Function Implementation Checklist**

| Feature | SDK Function / Class | Configuration Detail |
| :---- | :---- | :---- |
| **Model Config** | genai.Client() | Initializes the client using the environment's GEMINI\_API\_KEY. |
| **Agent Persona** | types.GenerateContentConfig(system\_instruction=...) | Define the **Senior Triage Specialist** persona. |
| **Multimodal Input** | client.models.generate\_content(contents=\[...\]) | The contents array must contain **4 Part objects**: Text, Image, Tabular Summary, Time-Series Trend. |
| **Image Part** | types.Part.from\_bytes(data=..., mime\_type="image/jpeg") | Used to ingest the X-ray image (must be base64 encoded by the host app). |
| **Structured Output** | config.response\_mime\_type="application/json" config.response\_schema=... | Enforces the final Diagnostic Report JSON structure. |
| **Function Definition** | The Python function itself (calculate\_sepsis\_risk) | Must be defined in tools.py with type hints for parameters. |
| **Tool Exposure** | config.tools=\[function1, function2\] | Exposes Python functions to the model for autonomous calling. |
| **Function Call Handling** | Checking response.function\_calls and executing tool/feeding result back. | Requires multi-turn chat logic in app.py. |

## **IV. Required Code Structures for Complex Features**

### **A. Multimodal Input Payload Structure**

The contents array combines all four modalities into a single request.

\# Helper to prepare the base64 data for the Part object  
def file\_to\_part(base64\_data, mime\_type):  
    return types.Part.from\_bytes(data=base64.b64decode(base64\_data), mime\_type=mime\_type)

\# Example of the final contents array for one API call  
patient\_contents \= \[  
    \# 1\. Text Data  
    types.Part.from\_text(f"Patient Notes: {user\_input\_text}"),  
      
    \# 2\. Image Data (X-ray base64)  
    file\_to\_part(uploaded\_image\_base64, "image/jpeg"),   
      
    \# 3\. Tabular Data (Pre-processed Language Feature)  
    types.Part.from\_text(f"Lab Summary (Tabular Data Feature): {tabular\_summary\_string}"),  
      
    \# 4\. Time-Series Data (Pre-processed Language Feature)  
    types.Part.from\_text(f"Vitals Trend (Time-Series Feature): {timeseries\_trend\_string}"),  
      
    \# Final Instruction  
    types.Part.from\_text("Synthesize all data. Use the tools. Provide final JSON report.")  
\]

### **B. Tool Definition and Function Calling Implementation**

This includes the use of Matplotlib for the visualization tool.

\# Function 2: Autonomous Visualization (Requires Matplotlib)  
def generate\_vitals\_visualization(time\_series\_data: str) \-\> str:  
    """  
    Executes Python code to plot time-series vitals (SpO2, HR)   
    for graphical analysis and returns the resulting PNG as a Base64 string.  
    """  
    \# 1\. Parse data string (JSON string expected from agent)  
    data \= json.loads(time\_series\_data)  
      
    \# 2\. Plot using Matplotlib  
    fig, ax \= plt.subplots(figsize=(6, 4))  
    ax.plot(\[d\['time'\] for d in data\], \[d\['spo2'\] for d in data\], label='SpO2 (%)', color='teal', marker='o')  
    ax.set\_title("Vitals Trend Confirmation", fontsize=10)  
    ax.legend(loc='lower left', fontsize=8)  
    ax.grid(axis='y', linestyle='--')  
      
    \# 3\. Save plot to buffer and encode to Base64  
    buf \= io.BytesIO()  
    plt.savefig(buf, format='png', bbox\_inches='tight')  
    plt.close(fig)  
    base64\_image \= base64.b64encode(buf.getvalue()).decode('utf-8')  
      
    return base64\_image  
      
\# Function 1: Sepsis Risk Calculator   
def calculate\_sepsis\_risk(heart\_rate: int, blood\_pressure: int, lactate\_level: float, respiratory\_rate: int) \-\> dict:  
    \# Simplified clinical logic for hackathon  
    score \= (heart\_rate // 10\) \+ (respiratory\_rate // 5\) \+ (lactate\_level \* 3\)  
    return {"risk\_score": int(score), "score\_category": "High Risk" if score \>= 20 else "Low Risk"}

\# Tools list for the API call  
TOOL\_CONFIG \= \[calculate\_sepsis\_risk, generate\_vitals\_visualization\]

### **C. Structured Output Schema**

DIAGNOSTIC\_REPORT\_SCHEMA \= types.Schema(  
    type=types.Type.OBJECT,  
    properties={  
        "differential\_diagnosis": types.Schema(  
            type=types.Type.ARRAY,   
            description="List of top 3 competing clinical hypotheses.",  
            items=types.Schema(type=types.Type.STRING)  
        ),  
        "triage\_urgency": types.Schema(  
            type=types.Type.STRING,   
            description="The final triage category.",  
            enum=\["RED", "YELLOW", "GREEN"\]  
        ),  
        "confidence\_score": types.Schema(  
            type=types.Type.NUMBER,   
            description="The agent's confidence in the primary diagnosis (0.0 to 1.0)."  
        ),  
        "evidence\_summary": types.Schema(  
            type=types.Type.STRING,   
            description="A concise summary of the cross-modal evidence supporting the diagnosis."  
        ),  
        "tool\_verification\_data": types.Schema(  
            type=types.Type.OBJECT,   
            description="Contains results from the function calls (risk score, visualization base64)."  
        ),  
    },  
)  
