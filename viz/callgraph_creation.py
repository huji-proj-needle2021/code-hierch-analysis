""" A very basic interface for generating a Java callgraph using
    a web UI instead of CLI
"""

from dash import html, dcc, Input, Output, State
from dash.development.base_component import Component
from dash.exceptions import PreventUpdate
from graph_import import Args, GEN_CALLGRAPH_JAR, GRAPH_DIR
from pathlib import Path
from .app import app, field
import tempfile
import base64

graph_create = html.Div(children=[
    html.H2(children="Callgraph generation options"),

    dcc.Loading(children=[
    field(f"Name of output folder containing graph (will be placed under {GRAPH_DIR.resolve()} ",
          dcc.Input(id="out_dir", type="text", placeholder="Name of folder",
                    value="jadx")),

    field("All .jar files needed to run the executable (the executable itself and everthing in its classpath, but not Java standard libraries)",
          dcc.Upload(id="jars", children=html.Div([
              'Drag and drop .jar files/click to upload ',
          ]), style={
              'width': '100%',
              'height': '60px',
              'lineHeight': '60px',
              'borderWidth': '1px',
              'borderStyle': 'dashed',
              'borderRadius': '5px',
              'textAlign': 'center',
              'margin': '10px'
          },
              # Allow multiple files to be uploaded
              multiple=True
          )),

    html.Pre(id="cur_files", children=[]),

    field("Identifier of main class (that contains the 'main' function)",
          dcc.Input(id="main_identifier", type="text", placeholder="Type a fully qualified class name, e.g, com.foo.MainClass",
                    value="jadx.gui.JadxGUI")),

    field("Words that should appear in a .jar filename. A filename without any of these words will be skipped in the analysis "
          "even if it was included in the classpath",
          dcc.Dropdown(id="jar_filter", multi=True, placeholder="Type any word, e.g 'jadx' ",
                       value=["jadx"], options=["jadx"])),

    field("Words that should appear in an edge's source and target identifiers. An edge without any of these words(as both source and target) will be skipped",
          dcc.Dropdown(id="edge_filter", multi=True, placeholder="Type any word, e.g 'jadx' ",
                       value=["jadx"], options=["jadx"])),

    html.Button("Create callgraph", id="create_cg"),
    html.Pre(id="graph_state"),
    ])
])


# a hacky way of using a dropdown input
# for arbitrary input
def multi_input(search_value, value):
    if not search_value:
        raise PreventUpdate
    existing = {v: v for v in value} if value else {}
    return {**existing, search_value: search_value}

edge_filter = app.callback(
    Output("edge_filter", "options"),
    Input("edge_filter", "search_value"),
    State("edge_filter", "value")
)(multi_input)


@app.callback(
    Output("cur_files", "children"),
    Input("jars", "filename")
)
def files_to_be_uploaded(filenames):
    if filenames and len(filenames) > 0:
        return "Files that will be uploaded: " + ", ".join(filenames)
    return ""

@app.callback(
    dict(graph_state=Output("graph_state", "children"),
         import_dir=Output("import_dir", "value")
         ),
    Input("create_cg", "n_clicks"),
    State("out_dir", "value"),
    State("jar_filter", "value"),
    State("edge_filter", "value"),
    State("main_identifier", "value"),
    State("graph_state", "children"),
    State("import_dir", "value"),
    State("jars", "filename"),
    State("jars", "contents")
)
def create_callgraph(n_clicks, out_dir, jar_filter, edge_filter, main_identifier, graph_state, import_dir, jar_filenames, jar_contents):
    if n_clicks:
        print("Trying to fetch callgraph")
        with tempfile.TemporaryDirectory("jar_dir") as input_jar_folder:
            for filename, content in zip(jar_filenames, jar_contents):
                if not filename.endswith("jar"):
                    print(f"Given non .jar file {filename}, skipping")
                    continue
                filename = Path(filename).parts[-1]
                content_type, base64_content = content.split(',')
                with open(Path(input_jar_folder) / filename, 'wb') as output_jar:
                    try:
                        decoded = base64.b64decode(base64_content, validate=True)
                    except Exception as e:
                        print(f"could not decode {filename}, skipping: {e}")
                        continue
                    output_jar.write(decoded)
                    print(f".jar file '{filename}' with content type '{content_type}' of {len(decoded)} bytes was copied into {input_jar_folder}")
            args = Args(
                input_jar_folder=Path(input_jar_folder).resolve(),
                edge_filter=list(edge_filter) if edge_filter else [],
                jar_filter=list(jar_filter) if jar_filter else [],
                main_class_identifier=main_identifier,
                graph_output_folder=(GRAPH_DIR / out_dir).resolve(),
            )
            cg = args.run_callgraph(GEN_CALLGRAPH_JAR, force_regen=True)
            graph_state=(f"Created a graph with {len(cg.vertices)} nodes and {len(cg.edges)} edges\n"
                        f"graph was saved under the name {out_dir}")
            return dict(graph_state=graph_state,
                        import_dir=out_dir)
    return dict(graph_state=graph_state, import_dir=import_dir)