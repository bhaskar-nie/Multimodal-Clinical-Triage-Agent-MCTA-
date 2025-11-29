from __future__ import annotations

from typing import Literal, Optional

import streamlit as st

# Hour 6-7: Color mapping for professional UI styling
STATUS_COLORS = {
    # Urgency colors (from Frontend Spec)
    "RED": "#DC2626",  # Red-600
    "YELLOW": "#F59E0B",  # Amber-500
    "GREEN": "#059669",  # Green-600
    # Risk category colors
    "HIGH_RISK": "#F97316",  # Orange-500 (for High Risk sepsis score)
    "LOW_RISK": "#0D9488",  # Teal-600 (for Low Risk sepsis score)
    # Accent colors
    "TEAL": "#0D9488",  # Teal-600 (Primary accent)
    "TEAL_LIGHT": "#A7F3D0",  # Teal-200 (Light backgrounds)
    "AMBER": "#F59E0B",  # Amber-500 (Warning/ACTION)
    "ORANGE": "#F97316",  # Orange-500 (High Risk)
    # Text colors
    "RED_TEXT": "#DC2626",
    "GREEN_TEXT": "#059669",
    "AMBER_TEXT": "#F59E0B",
    "ORANGE_TEXT": "#F97316",
    "TEAL_TEXT": "#0D9488",
    # Border colors
    "TEAL_BORDER": "#0D9488",
    "ORANGE_BORDER": "#F97316",
    "AMBER_BORDER": "#F59E0B",
    "RED_BORDER": "#DC2626",
}


def render_triage_badge(urgency: Optional[str]) -> None:
    """
    Render a large, visually dominating triage urgency badge.
    
    Hour 6-7: Enhanced to be immediately obvious with larger size,
    prominent color coding, and professional styling.
    """
    if not urgency:
        st.markdown(
            """
            <div style="
                border-radius: 0.75rem;
                padding: 1.5rem;
                background-color: #F3F4F6;
                color: #6B7280;
                font-weight: 600;
                font-size: 1.1rem;
                text-align: center;
                border: 2px dashed #D1D5DB;
            ">
                🩺 Triage Urgency<br/>
                <span style="font-size: 0.9rem; font-weight: 400;">No triage result yet.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    urgency = urgency.upper()
    color = STATUS_COLORS.get(urgency, "#6B7280")
    
    # Determine icon based on urgency
    icon_map = {
        "RED": "🚨",
        "YELLOW": "⚠️",
        "GREEN": "✅",
    }
    icon = icon_map.get(urgency, "🩺")

    st.markdown(
        f"""
        <div style="
            border-radius: 0.75rem;
            padding: 1.75rem 2rem;
            background-color: {color};
            color: white;
            font-weight: 800;
            font-size: 1.5rem;
            text-align: center;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.15), 0 10px 10px -5px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
            border: 2px solid rgba(255,255,255,0.2);
        ">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">{icon}</div>
            <div style="font-size: 0.9rem; font-weight: 600; opacity: 0.95; margin-bottom: 0.3rem;">
                TRIAGE URGENCY
            </div>
            <div style="font-size: 2rem; letter-spacing: 0.1em;">
                {urgency}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card(title: str, body: str, icon: str = "") -> None:
    st.markdown(
        f"""
        <div style="
            background-color: #FFFFFF;
            border-radius: 0.75rem;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 0.75rem;
            border: 1px solid #E5E7EB;
        ">
            <div style="font-weight: 600; margin-bottom: 0.5rem; color: #0F172A;">
                {icon} {title}
            </div>
            <div style="font-size: 0.9rem; color: #4B5563; white-space: pre-wrap;">
                {body}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tool_action(message: str, kind: Literal["ACTION", "OBSERVATION", "ERROR"] = "ACTION"):
    """
    Render tool action log entries with color-coded styling.
    
    - ACTION: Amber/Orange border (Model Request)
    - OBSERVATION: Teal border (Host Execution Result)
    - ERROR: Red border (Error/Failure)
    """
    if kind == "ACTION":
        bg = "#FEF3C7"  # Amber-100
        border_color = STATUS_COLORS["AMBER_BORDER"]
        prefix = "[ACTION]"
        icon = "🔧"
    elif kind == "OBSERVATION":
        bg = "#CCFBF1"  # Teal-100
        border_color = STATUS_COLORS["TEAL_BORDER"]
        prefix = "[OBSERVATION]"
        icon = "✅"
    else:  # ERROR
        bg = "#FEE2E2"  # Red-100
        border_color = STATUS_COLORS["RED_BORDER"]
        prefix = "[ERROR]"
        icon = "❌"

    st.markdown(
        f"""
        <div style="
            background-color: {bg};
            border-left: 4px solid {border_color};
            border-radius: 0.5rem;
            padding: 0.6rem 0.8rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        ">
            <strong style="color: {border_color};">{icon} {prefix}</strong> 
            <span style="color: #1F2937;">{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_system_status() -> None:
    """Render system status header."""
    st.markdown(
        """
        <div style="
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: #111827;
            color: #A7F3D0;
            padding: 0.6rem 0.8rem;
            border-radius: 0.75rem;
            margin-bottom: 0.75rem;
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <span style="font-size: 0.9rem; color: #6EE7B7; font-weight: 600;">MCTA · Multimodal Clinical Triage Agent</span>
        </div>
        """,
        unsafe_allow_html=True,
    )



