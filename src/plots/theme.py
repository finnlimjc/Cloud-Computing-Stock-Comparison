# Company palette: A is dark blue, B is gold
COLOR_A = "#12264F"
COLOR_B = "#C7A15E"
FILL_A = "rgba(18,38,79,0.14)"
FILL_B = "rgba(199,161,94,0.18)"

# Shared chart theme
COLOR_INK = "#17233d"
COLOR_MUTED = "#5f6b7f" # de-emphasize text
COLOR_RULE = "#e2e7ef" #divider, gridlines
COLOR_BG = "#ffffff"
COLOR_SECTION_FILL = "#eef2f8"
FONT_STACK = "Work Sans, Helvetica Neue, Arial, sans-serif"
MONO_STACK = "IBM Plex Mono, SF Mono, Menlo, monospace"

def chart_title(text:str, size:int, **layout:object) -> dict:
    """
    Build a left-aligned Plotly title in the shared ink color and font.
    
    Inputs:
    - text: title text
    - size: title font size in points
    - layout: extra Plotly title properties, such as y or yanchor
    
    Outputs:
    - Plotly title dict to pass as the title of a figure layout
    """
    font = dict(size=size, color=COLOR_INK, family=FONT_STACK)
    title = dict(text=text, font=font, x=0.01, xanchor="left", **layout)
    return title

def legend_font() -> dict:
    """Build the shared Plotly legend font."""
    font = dict(color=COLOR_INK, size=12, family=FONT_STACK)
    return font
