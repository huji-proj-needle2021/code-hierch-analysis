from .app import app, field
from dash import html, dcc, Input, Output, State
from git_analysis import HierarchyType
from graph_import import *
from pathlib import Path
import igraph




graph_import = html.Div(children=[
    html.H2(children="Graph import and visualization options"),
    field("Graph import directory",
          dcc.Dropdown(id="import_dir", placeholder="Graph folder(within GRAPH dir)", options=[])),
    html.Pre(id="graph_description", children=""),
    field("Java Hierarchy",
          dcc.Dropdown(id="hierch",
                       options=[], disabled=True
                       )),
    field("Maximal number of nodes",
          dcc.Slider(id="max_nodes", min=0, max=0, value=0)),
    field("Maximal number of edges",
          dcc.Slider(id="max_edges", min=0, max=0, value=0)),
    html.Button("Load all possible", id="refresh"),
    dcc.Store(id="graph_active")
])



@app.callback(
    dict(options=Output("import_dir", "options"),
         graph_active=Output("graph_active", "data"),
         desc=Output("graph_description", "children"),
         possible_hierch=Output("hierch", "options"),
         hierch_disabled=Output("hierch", "disabled"),
         hierch=Output("hierch", "value")
         ),
    Input("import_dir", "value")
)
def graph_import_dir(import_dir):
    graph_active = False
    options = [f.parts[-1] for f in GRAPH_DIR.iterdir() if f.is_dir()]
    possible_hierch = []
    hierch_disabled = True
    desc=""
    hierch = None
    if import_dir in options:
        graph_active = True
        graph = GraphData.from_folder(GRAPH_DIR / import_dir)
        desc = json.dumps({
            "type": graph.type,
            "hierarch": graph.hierch,
            "#vertices": len(graph.vertices),
            "#edges": len(graph.edges),
            **graph.attrs,
            "hash": graph.hash
        }, indent=2)
        hierch_disabled = False
        possible_hierch = [h.name for h in graph.hierch.included()]
        hierch = possible_hierch[0]
    return dict(
        options=options,
        graph_active=graph_active,
        desc=desc,
        possible_hierch=possible_hierch,
        hierch_disabled=hierch_disabled,
        hierch=hierch
    )
