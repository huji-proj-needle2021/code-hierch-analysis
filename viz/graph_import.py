from .app import app, field
from dash import html, dcc, Input, Output, State
from git_analysis import HierarchyType
from graph_import import RawGraph, raw_graph_to_igraph, igraph_to_cytoscape_fig
from pathlib import Path

DEFAULT_MAX_NODES = 250
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
          dcc.Slider(id="max_nodes", min=0, max=DEFAULT_MAX_NODES, value=DEFAULT_MAX_NODES)),
    field("Maximal number of edges",
          dcc.Slider(id="max_edges", min=0, max=DEFAULT_MAX_EDGES, value=DEFAULT_MAX_EDGES)),
    html.Button("Import graph", id="import")
])

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