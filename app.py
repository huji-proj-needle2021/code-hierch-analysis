# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from re import search
import tempfile
from typing import Optional
from dash import Dash, html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_cytoscape as cyto
import plotly.express as px
import pandas as pd
from graph_import import Args, GEN_CALLGRAPH_JAR, JAR_FOLDER, OUTPUT_FOLDER
from pathlib import Path
import logging

app = Dash(__name__)

# assume you have a "long-form" data frame
# see https://plotly.com/python/px-arguments/ for more options
df = pd.DataFrame({
    "Fruit": ["Apples", "Oranges", "Bananas", "Apples", "Oranges", "Bananas"],
    "Amount": [4, 1, 2, 2, 4, 5],
    "City": ["SF", "SF", "SF", "Montreal", "Montreal", "Montreal"]
})

fig = px.bar(df, x="Fruit", y="Amount", color="City", barmode="group")

# import_args = Args(
#     edge_filter=["jadx"],
#     jar_filter=["jadx"],
#     input_jar_folder=JAR_FOLDER,
#     graph_output_folder=OUTPUT_FOLDER,
#     main_class_identifier="jadx.gui.JadxGUI",
# )

graph_import = html.Div(children=[
    html.H2(children="Callgraph import options"),

    html.Label(children="Graph directory where the call graph will be created and imported from", htmlFor="out_dir"),
    dcc.Input(id="out_dir", type="text", placeholder="Folder that will contain graph data",
              value="graphImport"),


    html.Label(children="Folder that contains .jar files for generating a call graph", htmlFor="jar_dir"),
    dcc.Input(id="jar_dir", type="text", placeholder="Folder containing .jar files",
              value="C:\\dev\\genCallgraph\\toAnalyze"),

    html.Label(children="Identifier of main class (that contains the 'main' function)", htmlFor="main_identifier"),
    dcc.Input(id="main_identifier", type="text", placeholder="Type a fully qualified class name, e.g, com.foo.MainClass",
              value="jadx.gui.JadxGUI"),

    html.Label(children="Words that should appear in a .jar file. A file without any of these words will be skipped", htmlFor="jar_filter"),
    dcc.Dropdown(id="jar_filter", multi=True, placeholder="Type any word, e.g 'jadx' "),

    html.Label(children="Words that should appear in an edge's source and target identifiers. An edge without any of these words will be skipped", htmlFor="edge_filter"),
    dcc.Dropdown(id="edge_filter", multi=True, placeholder="Type any word, e.g 'jadx' ",
                 value=["jadx"]),

    html.Button("Import", id="import"),
    dcc.Store(id="callgraph", storage_type="memory")
])

graph_state_div = html.Div(children=[
    html.H2(id="graph_state")
])

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
    Output("callgraph", "data"),
    Input("import", "n_clicks"),
    State("out_dir", "value"),
    State("jar_dir", "value"),
    State("edge_filter", "value"),
    State("jar_filter", "value"),
    State("main_identifier", "value"),
)
def fetch_callgraph(n_clicks, out_dir, jar_dir, edge_filter, jar_filter, main_identifier):
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
        return {
            "nodes": cg.node_props.to_dict(orient='index'),
            "edges": cg.edges.to_dict(orient='records')
        }
    return None

@app.callback(
    Output("graph_state", "children"),
    Input("callgraph", "data")
)
def graph_state(callgraph):
    if not callgraph:
        return "Not loaded yet"
    return f'Graph with {len(callgraph["nodes"])} nodes and {len(callgraph["edges"])} edges'

app.layout = html.Div(children=[
    html.H1(children='Needle in a Data Haystack: Analysis of Java call graph'),
    graph_import,
    graph_state_div,
    dcc.Graph(
        id='example-graph',
        figure=fig
    )
])

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("graph_import").setLevel(logging.INFO)
    app.run_server(debug=True)
