# Company palette: A is dark blue, B is gold; C-E extend it for multi-stock comparisons
COLOR_A = "#12264F"
COLOR_B = "#C7A15E"
COLOR_C = "#2E8B7A"
COLOR_D = "#C0504D"
COLOR_E = "#7B6FB0"

# Shared chart theme
COLOR_INK = "#17233d"
COLOR_MUTED = "#3f4a5cff" # de-emphasize text
COLOR_RULE = "#e2e7ef" #divider, gridlines
COLOR_BG = "#ffffff"
FONT_STACK = "Work Sans, Helvetica Neue, Arial, sans-serif"
MONO_STACK = "IBM Plex Mono, SF Mono, Menlo, monospace"

def with_alpha(hex_color:str, alpha:float) -> str:
    """Convert a #RRGGBB color to an rgba() string with the given opacity."""
    red, green, blue = (int(hex_color[position:position + 2], 16) for position in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"

def legend_font() -> dict:
    """Build the shared Plotly legend font."""
    font = dict(color=COLOR_INK, size=14, family=FONT_STACK)
    return font

def hover_label() -> dict:
    """Build the shared Plotly hover box, larger than the default so it stays readable."""
    label = dict(bgcolor=COLOR_BG, bordercolor=COLOR_RULE, font=dict(color=COLOR_INK, size=14, family=FONT_STACK))
    return label
