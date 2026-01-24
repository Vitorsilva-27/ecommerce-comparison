"""Theme management for the E-commerce Comparison UI."""

import streamlit as st

# Theme configurations
THEMES = {
    "light": {
        "name": "Light",
        "icon": "sun",
        "backgroundColor": "#FFFFFF",
        "secondaryBackgroundColor": "#F0F2F6",
        "textColor": "#262730",
        "primaryColor": "#FF4B4B",
        "cardBackground": "#FFFFFF",
        "borderColor": "#E0E0E0",
        "successColor": "#28A745",
        "errorColor": "#DC3545",
        "warningColor": "#FFC107",
        "infoColor": "#17A2B8",
    },
    "dark": {
        "name": "Dark",
        "icon": "moon",
        "backgroundColor": "#0E1117",
        "secondaryBackgroundColor": "#262730",
        "textColor": "#FAFAFA",
        "primaryColor": "#FF4B4B",
        "cardBackground": "#1E1E1E",
        "borderColor": "#3D3D3D",
        "successColor": "#00D26A",
        "errorColor": "#FF6B6B",
        "warningColor": "#FFD93D",
        "infoColor": "#6BCBFF",
    }
}


def init_theme():
    """Initialize theme in session state."""
    if "theme" not in st.session_state:
        st.session_state.theme = "light"


def get_current_theme() -> dict:
    """Get current theme configuration."""
    init_theme()
    return THEMES.get(st.session_state.theme, THEMES["light"])


def toggle_theme():
    """Toggle between light and dark theme."""
    init_theme()
    st.session_state.theme = "dark" if st.session_state.theme == "light" else "light"


def render_theme_toggle():
    """Render theme toggle button in sidebar."""
    init_theme()

    current = st.session_state.theme
    is_dark = current == "dark"

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Theme")

    # Display current mode with icon
    current_icon = "Dark Mode" if is_dark else "Light Mode"
    st.sidebar.markdown(f"**Current:** {current_icon}")

    # Toggle button
    button_label = "Switch to Light Mode" if is_dark else "Switch to Dark Mode"
    if st.sidebar.button(button_label, key="theme_toggle", use_container_width=True):
        toggle_theme()
        st.rerun()


def apply_theme_css():
    """Apply theme CSS to the page."""
    init_theme()
    theme = get_current_theme()

    css = f"""
    <style>
        /* Main background */
        .stApp {{
            background-color: {theme['backgroundColor']};
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: {theme['secondaryBackgroundColor']};
        }}

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: {theme['textColor']};
        }}

        /* Text colors */
        .stMarkdown, .stText, p, span, label {{
            color: {theme['textColor']} !important;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: {theme['textColor']} !important;
        }}

        /* Metric values */
        [data-testid="stMetricValue"] {{
            color: {theme['textColor']} !important;
        }}

        [data-testid="stMetricLabel"] {{
            color: {theme['textColor']} !important;
        }}

        /* Cards and containers */
        [data-testid="stExpander"] {{
            background-color: {theme['secondaryBackgroundColor']};
            border-color: {theme['borderColor']};
        }}

        /* Dataframes */
        .stDataFrame {{
            background-color: {theme['cardBackground']};
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {theme['secondaryBackgroundColor']};
        }}

        .stTabs [data-baseweb="tab"] {{
            color: {theme['textColor']};
        }}

        /* Input fields */
        .stTextInput > div > div > input {{
            background-color: {theme['secondaryBackgroundColor']};
            color: {theme['textColor']};
        }}

        .stSelectbox > div > div {{
            background-color: {theme['secondaryBackgroundColor']};
            color: {theme['textColor']};
        }}

        /* Radio buttons */
        .stRadio > div {{
            color: {theme['textColor']};
        }}

        /* Buttons */
        .stButton > button {{
            background-color: {theme['primaryColor']};
            color: white;
            border: none;
        }}

        .stButton > button:hover {{
            background-color: {theme['primaryColor']};
            opacity: 0.8;
        }}

        /* Success, error, warning, info messages */
        .stSuccess {{
            background-color: {theme['successColor']}20;
            color: {theme['successColor']};
        }}

        .stError {{
            background-color: {theme['errorColor']}20;
            color: {theme['errorColor']};
        }}

        .stWarning {{
            background-color: {theme['warningColor']}20;
            color: {theme['warningColor']};
        }}

        .stInfo {{
            background-color: {theme['infoColor']}20;
            color: {theme['infoColor']};
        }}

        /* Code blocks */
        .stCodeBlock {{
            background-color: {theme['secondaryBackgroundColor']};
        }}

        code {{
            background-color: {theme['secondaryBackgroundColor']};
            color: {theme['textColor']};
        }}

        /* Tables */
        .stTable {{
            background-color: {theme['cardBackground']};
        }}

        .stTable th {{
            background-color: {theme['secondaryBackgroundColor']};
            color: {theme['textColor']};
        }}

        .stTable td {{
            color: {theme['textColor']};
        }}

        /* Dividers */
        hr {{
            border-color: {theme['borderColor']};
        }}

        /* JSON viewer */
        .stJson {{
            background-color: {theme['secondaryBackgroundColor']};
        }}

        /* Caption text */
        .stCaption {{
            color: {theme['textColor']};
            opacity: 0.7;
        }}

        /* Plotly charts - adjust for dark mode */
        .js-plotly-plot .plotly .modebar {{
            background-color: transparent !important;
        }}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)


def get_plotly_theme() -> str:
    """Get Plotly template name based on current theme."""
    init_theme()
    return "plotly_dark" if st.session_state.theme == "dark" else "plotly_white"


def get_plotly_layout_updates() -> dict:
    """Get Plotly layout updates for current theme."""
    init_theme()
    theme = get_current_theme()

    return {
        "paper_bgcolor": theme["backgroundColor"],
        "plot_bgcolor": theme["secondaryBackgroundColor"],
        "font": {"color": theme["textColor"]},
        "xaxis": {
            "gridcolor": theme["borderColor"],
            "zerolinecolor": theme["borderColor"],
        },
        "yaxis": {
            "gridcolor": theme["borderColor"],
            "zerolinecolor": theme["borderColor"],
        }
    }
