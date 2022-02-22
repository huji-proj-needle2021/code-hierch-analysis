from dash import Dash, html
from dash.development.base_component import Component
import dash_cytoscape as cyto

cyto.load_extra_layouts()
app = Dash(__name__)

def field(label: str, input: Component):
    return html.Div(children=[
        html.Label(children=label, htmlFor=input.id),
        input
    ], className="formField")