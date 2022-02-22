# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from re import search
import tempfile
from typing import Optional
from dash import Dash, html, dcc, Input, Output, State
from dash.development.base_component import Component
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto
import plotly.express as px
import pandas as pd
from git_analysis.java_type import HierarchyType
from graph_import import Args, GEN_CALLGRAPH_JAR, JAR_FOLDER, OUTPUT_FOLDER, RawGraph, raw_graph_to_igraph, igraph_to_cytoscape_fig
from pathlib import Path
import logging

app = Dash(__name__)


def field(label: str, input: Component):
    return html.Div(children=[
        html.Label(children=label, htmlFor=input.id),
        input
    ], className="formField")

graph_create_status = html.Div(children=[
    dcc.Loading(id="creating", type="default", children=[
        html.H3(id="graph_state")
    ])
])

graph_create = html.Div(children=[
    html.H2(children="Callgraph generation options"),

    # html.Label(children="Graph directory where the call graph will be created and imported from", htmlFor="out_dir"),
    # dcc.Input(id="out_dir", type="text", placeholder="Folder that will contain graph data",
    #           value="graphImport-jadx"),
    field("Output folder for generated callgraph (where it can be imported from)",
          dcc.Input(id="out_dir", type="text", placeholder="Folder that will contain graph data",
                    value="graphImport-jadx")),

    field("Folder that contains .jar files for generating a call graph",
          dcc.Input(id="jar_dir", type="text", placeholder="Folder containing .jar files",
                    value="C:\\dev\\genCallgraph\\toAnalyze")),

    field("Identifier of main class (that contains the 'main' function)",
          dcc.Input(id="main_identifier", type="text", placeholder="Type a fully qualified class name, e.g, com.foo.MainClass",
                    value="jadx.gui.JadxGUI")),

    field("Words that should appear in a .jar file. A file without any of these words will be skipped",
          dcc.Dropdown(id="jar_filter", multi=True, placeholder="Type any word, e.g 'jadx' ",
                       value=["jadx"])),


    field("Words that should appear in an edge's source and target identifiers. An edge without any of these words will be skipped",
          dcc.Dropdown(id="edge_filter", multi=True, placeholder="Type any word, e.g 'jadx' ",
                       value=["jadx"])),

    html.Button("Create callgraph", id="create_cg"),
    graph_create_status,
])


field("Java Hierarchy",
      dcc.Dropdown(id="hierch", placeholder="Type any word, e.g 'jadx' ",
                   options={
                                            variant.name: variant.name
                                            for variant in HierarchyType},
                   value=HierarchyType.method.name),
      )



DEFAULT_MAX_NODES = 1000
DEFAULT_MAX_EDGES = 1000

graph_import = html.Div(children=[
    html.H2(children="Graph import and visualization options"),
    field("Graph import directory",
          dcc.Input(id="import_dir", type="text", placeholder="Folder that contains graph data",
                    value="graphImport-jadx")
          ),
    field("Java Hierarchy",
          dcc.Dropdown(id="hierch", placeholder="Type any word, e.g 'jadx' ",
                       options={
                           variant.name: variant.name
                           for variant in HierarchyType},
                       value=HierarchyType.method.name),
          ),
    field("Maximal number of nodes",
          dcc.Slider(id="max_nodes", min=0, max=DEFAULT_MAX_NODES)),
    field("Maximal number of edges",
          dcc.Slider(id="max_edges", min=0, max=DEFAULT_MAX_EDGES)),
    html.Button("Import graph", id="import")
])

# a hacky way of using a dropdown input
# for arbitrary input
def multi_input(search_value, value):
    if not search_value:
        raise PreventUpdate
    existing = {v: v for v in value} if value else {}
    return {**existing, search_value: search_value}

jar_filter = app.callback(
    Output("jar_filter", "options"),
    Input("jar_filter", "search_value"),
    State("jar_filter", "value")
)(multi_input)

edge_filter = app.callback(
    Output("edge_filter", "options"),
    Input("edge_filter", "search_value"),
    State("edge_filter", "value")
)(multi_input)

@app.callback(
    dict(graph_state=Output("graph_state", "children"),
         import_dir=Output("import_dir", "value")
         ),
    Input("create_cg", "n_clicks"),
    State("out_dir", "value"),
    State("jar_dir", "value"),
    State("edge_filter", "value"),
    State("jar_filter", "value"),
    State("main_identifier", "value"),
    State("graph_state", "children"),
    State("import_dir", "value")
)
def create_callgraph(n_clicks, out_dir, jar_dir, edge_filter, jar_filter, main_identifier, graph_state, import_dir):
    if n_clicks:
        print("Trying to fetch callgraph")
        args = Args(
            input_jar_folder=Path(jar_dir).resolve(),
            edge_filter=list(edge_filter) if edge_filter else [],
            jar_filter=list(jar_filter) if jar_filter else [],
            main_class_identifier=main_identifier,
            graph_output_folder=Path(out_dir).resolve(),
        )
        cg = args.run_callgraph(GEN_CALLGRAPH_JAR)
        return dict(graph_state=f"Created a graph with {len(cg.node_props)} nodes and {len(cg.edges)} edges ",
                    import_dir=out_dir)
    return dict(graph_state=graph_state, import_dir=import_dir)


@app.callback(
    dict(cytoscape=Output("cytoscape", "elements"),
         max_nodes=Output("max_nodes", "max"),
         max_edges=Output("max_edges", "max")
         ),
    Input("import", "n_clicks"),
    State("import_dir", "value"),
    State("max_nodes", "value"),
    State("max_edges", "value"),
    State("hierch", "value")
)
def import_graph(n_clicks, import_dir, max_nodes, max_edges, hierch):
    if n_clicks:
        raw_graph = RawGraph.from_folder(Path(import_dir).resolve())
        graph = raw_graph_to_igraph(raw_graph, HierarchyType[hierch])
        elements = igraph_to_cytoscape_fig(graph, max_nodes or 0, max_edges or 0)
        return dict(cytoscape=elements, max_nodes=len(graph.vs), max_edges=len(graph.es))
    return dict(cytoscape=[], max_nodes=max_nodes or DEFAULT_MAX_NODES, max_edges=max_edges or DEFAULT_MAX_EDGES)

app.layout = html.Div(children=[
    dcc.Store(id="cur_raw_graph", storage_type="memory"),
    html.H1(children='Needle in a Data Haystack: Analysis of Java call graph'),
    graph_create,
    graph_import,
    cyto.Cytoscape(
        id='cytoscape',
        layout={'name': 'cose'},
        style={'width': '100%', 'height': '70vh'},
        elements=[
            {'data': {'id': 'one', 'label': 'Node 1'},
                'position': {'x': 75, 'y': 75}},
            {'data': {'id': 'two', 'label': 'Node 2'},
             'position': {'x': 200, 'y': 200}},
            {'data': {'source': 'one', 'target': 'two'}}
        ]
    )
])

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("graph_import").setLevel(logging.INFO)
    app.run_server(debug=True)
