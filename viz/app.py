from dash import Dash, html
from dash.development.base_component import Component
import dash_cytoscape as cyto
from flask_caching import Cache
from pathlib import Path

cyto.load_extra_layouts()
app = Dash(__name__)

CACHE_CONFIG = {
    'CACHE_TYPE': 'SimpleCache'
}
cache = Cache()
cache.init_app(app.server, config=CACHE_CONFIG)

def field(label: str, input: Component):
    return html.Div(children=[
        html.Label(children=label, htmlFor=input.id),
        input
    ], className="formField")