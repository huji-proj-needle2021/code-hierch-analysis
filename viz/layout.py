from dash import html, dcc
import dash_cytoscape as cyto
from .callgraph_creation import graph_create
from .graph_import import graph_import
from .app import app
from .graph import graph

layout = html.Div(children=[
    dcc.Store(id="cur_raw_graph", storage_type="memory"),
    html.H1(children='Needle in a Data Haystack: Analysis of Java call graph'),
    graph_create,
    graph_import,
    graph
])