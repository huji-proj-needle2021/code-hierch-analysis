""" A very basic interface for generating a Java callgraph using
    a web UI instead of CLI
"""

from dash import html, dcc, Input, Output, State
from dash.development.base_component import Component
from dash.exceptions import PreventUpdate
from graph_import import Args, GEN_CALLGRAPH_JAR
from pathlib import Path
from .app import app, field

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