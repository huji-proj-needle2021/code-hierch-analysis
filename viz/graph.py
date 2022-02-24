""" Based on https://raw.githubusercontent.com/plotly/dash-cytoscape/master/usage-elements.py
    modified to use our own graph
"""

import dash
from typing import Tuple
from dash import Input, Output, State, dcc, html

from git_analysis.java_type import HierarchyType
from graph.graph_logic import *
from .app import app, cache, field
from .graph_import import graph_params_to_state
import dash_cytoscape as cyto

import json

import dash_cytoscape as cyto
import viz.dash_reusable_components as drc
from pathlib import Path

from graph_import import *

default_stylesheet = [
    {
        "selector": 'node',
        'style': {
            "opacity": 0.65,
            'z-index': 9999,
            'background-color': 'data(color)',
            'color': 'data(color)'
        }
    },
    {
        "selector": 'edge',
        'style': {
            "curve-style": "bezier",
            "opacity": 0.45,
            'z-index': 5000
        }
    },
    {
        'selector': '.followerNode',
        'style': {
            'border-color': '#0074D9',
            "border-width": 2,
        }
    },
    {
        'selector': '.followerEdge',
        "style": {
            "mid-target-arrow-color": "blue",
            "mid-target-arrow-shape": "vee",
            "line-color": "#0074D9"
        }
    },
    {
        'selector': '.followingNode',
        'style': {
            'border-color': '#FF4136',
            "border-width": 2,
        }
    },
    {
        'selector': '.followingEdge',
        "style": {
            "mid-target-arrow-color": "red",
            "mid-target-arrow-shape": "vee",
            "line-color": "#FF4136",
        }
    },
    {
        "selector": '.genesis',
        "style": {
            'background-color': '#B10DC9',
            "border-width": 2,
            "border-color": "purple",
            "border-opacity": 1,
            "opacity": 1,

            "label": "data(label)",
            "color": "#B10DC9",
            "text-opacity": 1,
            "font-size": 12,
            'z-index': 9999
        }
    },
    {
        'selector': ':selected',
        "style": {
            "border-width": 2,
            "border-color": "black",
            "border-opacity": 1,
            "opacity": 1,
            "label": "data(label)",
            "color": "black",
            "font-size": 12,
            'z-index': 9999
        }
    },
    {
        'selector': '.selneighbor',
        "style": {
            "label": "data(label)",
            "color": "black",
            "font-size": 12,
            'z-index': 9999

        }
    }
]

# ################################# APP LAYOUT ################################
styles = {
    'json-output': {
        'overflow-y': 'scroll',
        'height': 'calc(50% - 25px)',
        'border': 'thin lightgrey solid'
    },
    'tab': {'height': 'calc(98vh - 80px)'},
    'graphAndTabs': {
        'display': 'flex',
        'flexDirection': 'row',
        # 'height': '70vh',
        'width': '100%'
    },
    'graphView': {
        'flex': '8'
    },
    'tabView': {
        'flex': '4'
    }
}



graph = html.Div(id="graphAndTabs", style={"display": "none"}, children=[
    html.Div(style=styles["graphView"], children=[
        cyto.Cytoscape(
            id='cytoscape',
            stylesheet=default_stylesheet,
            style={
                'height': '85vh',
                'width': '100%'
            }
        )
    ]),

    html.Div(style=styles["tabView"], children=[
        dcc.Tabs(id='tabs', children=[
            dcc.Tab(label='Control Panel', children=[
                drc.NamedDropdown(
                    name='Layout',
                    id='dropdown-layout',
                    options=drc.DropdownOptionsList(
                        'random',
                        'grid',
                        'circle',
                        'concentric',
                        'breadthfirst',
                        'cose'
                    ),
                    value='grid',
                    clearable=False
                ),
                drc.NamedRadioItems(
                    name='Graph expansion direction when clicking a node',
                    id='expansion_mode',
                    options=[
                        {'label': 'Both directions', 'value': 'all'},
                        {'label': 'Edges coming in', 'value': 'in'},
                        {'label': 'Edges coming out', 'value': 'out'},
                    ],
                    value='all'
                ),
                field("Focus on a new node:", html.Div(id="focus", children=[
                    dcc.Dropdown(id="package_dropdown", placeholder="Package name", options=[]),
                    dcc.Dropdown(id="typedef_dropdown", placeholder="Type def(class/interface/enum) name", options=[]),
                    dcc.Dropdown(id="method_dropdown", placeholder="Method name", options=[]),
                    html.Button(id="focus_button", children="Focus")
                ]))
            ]),

            dcc.Tab(label='JSON', children=[
                html.Div(style=styles['tab'], children=[
                    html.P('Node Object JSON:'),
                    html.Pre(
                        id='tap-node-json-output',
                        style=styles['json-output']
                    ),
                    html.P('Edge Object JSON:'),
                    html.Pre(
                        id='tap-edge-json-output',
                        style=styles['json-output']
                    )
                ])
            ])
        ]),

    ])
])

@app.callback(
    Output("graphAndTabs", "style"),
    Input("graph_active", "data")
)
def render_graph(graph_active):
    if graph_active:
        return styles["graphAndTabs"]
    return { "display": "none"}

# ############################## CALLBACKS ####################################
@app.callback(Output('tap-node-json-output', 'children'),
              [Input('cytoscape', 'tapNode')])
def display_tap_node(data):
    return json.dumps(data, indent=2)


@app.callback(Output('tap-edge-json-output', 'children'),
              [Input('cytoscape', 'tapEdge')])
def display_tap_edge(data):
    return json.dumps(data, indent=2)


@app.callback(Output('cytoscape', 'layout'),
              [Input('dropdown-layout', 'value')])
def update_cytoscape_layout(layout):
    return {'name': layout}


@app.callback(
    dict(
        new_options=dict(
            package=Output("package_dropdown", "options"),
            typedef=Output("typedef_dropdown", "options"),
            method=Output("method_dropdown", "options")
        ),
        focus_disabled=Output("focus_button", "disabled")
    ),
    inputs=dict(
        graph_active=State("graph_active", "data"),
        package=Input("package_dropdown", "value"),
        typedef=Input("typedef_dropdown", "value"),
        method=Input("method_dropdown", "value"),
        graph_params=Input("graph_params", "data"),
        old_options=dict(
            package=State("package_dropdown", "options"),
            typedef=State("typedef_dropdown", "options"),
            method=State("method_dropdown", "options")
        ),
    )
)
def update_search_options(graph_active, package, typedef, method, graph_params, old_options):
    new_options = old_options or { "package": [], "typedef": [], "method": []}
    if not graph_params or not graph_active:
        return { "new_options": new_options, "focus_disabled": True }
    state = graph_params_to_state(graph_params)
    verts = state.vertices_by_communities_prs


    def dfv_to_options(dfv: pd.Series):
        return [{
            "label": str(item),
            "value": str(item)
        } for item in dfv.unique()]

    new_options["package"] = dfv_to_options(
        verts["package"])
    if package and "class" in verts.columns:
        new_options["typedef"] = dfv_to_options(
            verts[verts["package"] == package]["class"])
    if typedef and "method" in verts.columns:
        new_options["method"] = dfv_to_options(
            verts[verts["class"] == typedef]["method"])
    
    can_focus = ((state.raw.hierch == HierarchyType.package and package) or
                 (state.raw.hierch == HierarchyType.type_def and typedef) or
                 (state.raw.hierch == HierarchyType.method and method)
    )

    return { "new_options": new_options, "focus_disabled": not can_focus }
    

@app.callback(Output('cytoscape', 'elements'),
              inputs=dict(
                  graph_active=Input("graph_active", "data"),
                  graph_params=Input("graph_params", "data"),
                  nodeData=Input("cytoscape", "tapNodeData"),
                  focus=Input("focus_button", "n_clicks"),
              ),
              state=dict(
                  focus_values=[State("package_dropdown", "value"),
                                State("typedef_dropdown", "value"),
                                State("method_dropdown", "value")],
                  elements=State("cytoscape", "elements"),
                  expansion_mode=State("expansion_mode", "value")
              ))
def generate_elements(graph_active, graph_params, nodeData, focus, focus_values, elements, expansion_mode):
    if not graph_active:
        return []
    graph = graph_params_to_state(graph_params).graph

    ctx = dash.callback_context
    if not ctx.triggered:
        return []

    changed_inputs =set(
        prop['prop_id'].split('.')[0] for prop in ctx.triggered
    )
    tappedANode = any("cytoscape.tapNodeData" in prop['prop_id'] for prop in ctx.triggered)

    focus_node = "focus_button" in changed_inputs
    reload_graph = any(v in changed_inputs for v in ("import_dir", "graph_params"))
    if focus_node:
        name = ".".join(str(val) for val in focus_values if val)
        found_genesis = False
        # check if the node we're looking for already exists in the graph
        for element in elements:
            element["classes"] = element["classes"].replace("genesis", "")
            if element.get("data").get("name") == name:
                found_genesis = True
                element["classes"] = element["classes"] + " genesis"
                break
        # otherwise, add it
        if not found_genesis:
            # TODO: sometimes this might fail to find, how is it possible?
            elements.append(igraph_vert_to_cyto(graph, graph.vs.find(name=name), classes=["genesis"]))
        
        return elements

    elif (not nodeData) or reload_graph:
        print("Graph is being reloaded")
        return [igraph_vert_to_cyto(graph, graph.vs[0], classes=["genesis"])]

    elif tappedANode:
        # tapped a node, try to expand
        do_expand = True
        # If the node has already been expanded, we don't expand it again
        if nodeData.get(f'expanded-{expansion_mode}') or nodeData.get('expanded-all'):
            do_expand = False

        # This retrieves the currently selected element, and tag it as expanded
        for element in elements:
            if nodeData['id'] == element.get('data').get('id'):
                element['data'][f'expanded-{expansion_mode}'] = True
                break
            
        neigh_nodes = graph.neighbors(nodeData['id'], expansion_mode)
        neigh_names = set(graph.vs[ix]["name"] for ix in neigh_nodes)
        neigh_edges = graph.incident(nodeData['id'], expansion_mode)
        node_class, edge_class = "", ""
        if expansion_mode == "in":
            node_class, edge_class = "followerNode", "followerEdge"
        elif expansion_mode == "out":
            node_class, edge_class = "followingNode", "followingEdge"

        if do_expand:
            elements.extend(igraph_vert_to_cyto(graph, graph.vs[node_ix], classes=[node_class, "selneighbor"]) for node_ix in neigh_nodes)
            elements.extend(igraph_edge_to_cyto(graph, graph.es[edge_ix], classes=[edge_class, "selneighbor"]) for edge_ix in neigh_edges)

        for element in elements:
            el_id = element.get('data').get('id')
            if el_id is None:
                continue
            if el_id not in neigh_names:
                element["classes"] = element["classes"].replace("selneighbor", "")
    return elements
    
