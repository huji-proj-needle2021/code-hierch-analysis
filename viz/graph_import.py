from .app import app, field, cache
from typing import Tuple
from dash import html, dcc, Input, Output, State
import plotly.express as px
import pandas as pd
from git_analysis import HierarchyType
from graph_import import GRAPH_DIR, ConversionArgs
from graph import raw_graph_to_igraph, GraphData
from pathlib import Path
import igraph
import json


@cache.memoize()
def fetch_graph(import_dir: str, args: ConversionArgs) -> Tuple[igraph.Graph, igraph.VertexClustering]:
    print(f"Fetching graph from {import_dir} with args {args}")
    raw = GraphData.from_folder(GRAPH_DIR / import_dir)
    ig, clusters = raw_graph_to_igraph(raw, args)
    print("Fetched graph and clustering successfully")

    return ig, clusters


graph_import = html.Div(children=[
    html.H2(children="Graph import and visualization options"),
    field("Graph import directory",
          dcc.Dropdown(id="import_dir", placeholder="Graph folder(within GRAPH dir)", options=[])),
    html.Pre(id="graph_description", children=""),
    dcc.Loading(children=[
        html.Div(
            id="graphOnly", style={"display": "none"}, children=[
                field("Java Hierarchy",
                      dcc.Dropdown(id="hierch",
                                   options=[], disabled=True
                                   )),
                field("Community detection resolution. 0: less communities, 1: more communities",
                      dcc.Slider(id="cd_resolution", min=0, max=1, value=1)),
                field("Community detection number of iterations (more iterations, more accurate)",
                      dcc.Slider(id="cd_iter", min=2, max=1000, value=2)),
                field("Page rank damping factor",
                      dcc.Slider(id="pr_damp", min=0, max=1, value=0.85)),
                dcc.Graph(id="community_graph"),
            ])]),
    dcc.Store(id="graph_active"),
    dcc.Store(id="graph_params")

])

@app.callback(
    Output("graph_params", "data"),
    inputs=dict(
        graph_params=dict(
            import_dir=Input("import_dir", "value"),
            hierch=Input("hierch", "value"),
            resolution=Input("cd_resolution", "value"),
            community_iters=Input("cd_iter", "value"),
            damping_factor=Input("pr_damp", "value")
        )
    )
)
def graph_params_callback(graph_params):
    return graph_params


def graph_params_to_graph(graph_params):
    import_dir = graph_params.pop("import_dir")
    args = ConversionArgs(**graph_params)
    return fetch_graph(import_dir, args)


@app.callback(
    [Output("community_graph", "figure"), 
     Output("community_graph", "style")
    ],
    Input("graph_active", "data"),
    Input("graph_params", "data"),
)
def community_graph(graph_active, graph_params):
    if not graph_active:
        return {}, { "display": "none" }
    _graph, clustering = graph_params_to_graph(graph_params)
    fig = px.histogram(clustering.membership,
                       title="Community membership histogram")
    fig.update_layout(xaxis_title="Community number")
    return fig, {}

@app.callback(
    dict(options=Output("import_dir", "options"),
         graph_active=Output("graph_active", "data"),
         desc=Output("graph_description", "children"),
         possible_hierch=Output("hierch", "options"),
         hierch_disabled=Output("hierch", "disabled"),
         hierch=Output("hierch", "value"),
         style=Output("graphOnly", "style")
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
    style = { "display": "none"}
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
        style = {}
    return dict(
        options=options,
        graph_active=graph_active,
        desc=desc,
        possible_hierch=possible_hierch,
        hierch_disabled=hierch_disabled,
        hierch=hierch,
        style=style
    )
