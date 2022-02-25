""" Based on https://raw.githubusercontent.com/plotly/dash-cytoscape/master/usage-elements.py
    Defines the graph visualization itself, and a side control panel.
"""

import dash
from typing import Iterable, Tuple
from dash import Input, Output, State, dcc, html

from git_analysis.java_type import HierarchyType
from graph.graph_logic import *
from .app import app, cache, field
from .graph_import import graph_params_to_state, GraphState
import dash_cytoscape as cyto

import json

import dash_cytoscape as cyto
import viz.dash_reusable_components as drc
from pathlib import Path

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
            "target-arrow-shape": "vee",
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
        'flex': '8',
        'border': '1px solid black'
    },
    'tabView': {
        'flex': '4'
    }
}


LAYOUTS = {
    'random': "random",
    'grid': "grid",
    'circle': "circle",
    'concentric': "concentric",
    'breadthfirst': "breadth-first: good for exploring by clicking around the graph.",
    'cose': "cose - force directed graph(good for visualizing communities)",
    'cola': "cola",
    'euler': "euler",
    'spread': "spread",
    'dagre': "dagre",
    'klay': "klay"
}

graph =  html.Div(id="graphAndTabs", style={"display": "none"}, children=[
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

    html.Div(id="tabView", style=styles["tabView"], children=[
        dcc.Tabs(id='tabs', children=[
            dcc.Tab(label='Control Panel', children=[
                drc.NamedDropdown(
                    name='Layout',
                    id='dropdown-layout',
                    options=LAYOUTS,
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
                        {'label': "Don't expand", 'value': 'dont'},
                    ],
                    value='all'
                ),
                field("Focus on a new node:", html.Div(id="focus", children=[
                    dcc.Dropdown(id="package_dropdown", placeholder="Package name", options=[]),
                    dcc.Dropdown(id="typedef_dropdown", placeholder="Type def(class/interface/enum) name", options=[]),
                    dcc.Dropdown(id="method_dropdown", placeholder="Method name", options=[]),
                    html.Button(id="focus_button", children="Focus")
                ])),
                html.P("Adding many nodes to the graph. The nodes are given from alternating communities, " +
                       "and sorted by page-ranks within each community."),
                field("Maximal number of nodes to add",
                      dcc.Slider(id="num_nodes_add", min=0, max=1000)),
                dcc.Checklist(id="add_edges", options=[
                              "Add edges spanned by these nodes too(can be heavy)"], value=[]),
                html.Button(id="add_button", children="Add"),

                dcc.Checklist(id="show_neigh_labels", options=[
                              "Show labels for neighbor nodes"], value=["Show labels for neighbor nodes"]),
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

@app.callback(Output("cytoscape", "stylesheet"), Input("show_neigh_labels", "value"))
def graph_stylesheet(show_neigh_labels):
    if len(show_neigh_labels) > 0:
        return default_stylesheet + [{
            'selector': '.selneighbor',
            "style": {
                "label": "data(label)",
                "color": "black",
                "font-size": 8,
                'z-index': 9999

            }
        }]
    return default_stylesheet

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
    """ Callback for updating dropdowns for searching a class/method/interface """
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

def add_nodes(state: GraphState, elements, num_nodes_to_add, add_edges_opt):
    """ Adds nodes(and possibly their edges) to the graph.
        The number of nodes being added is divided evenly among all communities,
        and within each community, added in descending order of page-rank values.
        This should ensure that the nodes added to the visualization are more
        representative, without biasing towards a particular dominant community.
    """
    if not num_nodes_to_add:
        return elements

    # first, determine candidate nodes -
    # those not already present in the graph
    existing_node_names = set(
        el.get("data").get("name") for el in elements
    )

    df = state.vertices_by_communities_prs
    df = df[~(df["name"].isin(existing_node_names))]


    if len(df) == 0:
        return elements

    # split the number of nodes added within each community,
    # evenly.
    communities = df.index.get_level_values(0).unique()
    n_communities = len(communities)
    take_per_comm = num_nodes_to_add // n_communities
    take_remainder = num_nodes_to_add % n_communities

    node_names = set()
    for ix, comm_ix in enumerate(communities):
        to_take = take_per_comm 
        if ix == 0:
            to_take += take_remainder
        node_names.update(df.loc[comm_ix].iloc[:to_take]["name"])


    new_node_names = node_names - existing_node_names
    new_nodes = state.graph.vs.select(name_in=new_node_names)

    new_elements = elements + [igraph_vert_to_cyto(state.graph, node, []) for node in new_nodes ]
    if add_edges_opt:
        subgraph = state.graph.induced_subgraph(new_nodes)
        new_edges = get_filtered_edges(elements, subgraph.es)
        new_elements.extend(igraph_edge_to_cyto(subgraph, edge, []) for edge in new_edges)

    return new_elements

def get_filtered_edges(elements, new_edges: Iterable[igraph.Edge]) -> Iterable[igraph.Edge]:
    """" Given the current cytoscape elements, and a set of edges
         to be added, filters them to avoid duplicate edges.
    """
    existing_edges = set(
        (el["data"]["source"], el["data"]["target"])
        for el in elements
        if el["data"].get("source") 
    )
    for edge in new_edges:
        from_name = edge.source_vertex["name"]
        to_name = edge.target_vertex["name"]
        if (from_name, to_name) not in existing_edges:
            yield edge

@app.callback(Output('cytoscape', 'elements'),
              inputs=dict(
                  graph_active=Input("graph_active", "data"),
                  graph_params=Input("graph_params", "data"),
                  nodeData=Input("cytoscape", "tapNodeData"),
                  focus=Input("focus_button", "n_clicks"),
                  add_edge=Input("add_button", "n_clicks")
              ),
              state=dict(
                  focus_values=[State("package_dropdown", "value"),
                                State("typedef_dropdown", "value"),
                                State("method_dropdown", "value")],
                  elements=State("cytoscape", "elements"),
                  expansion_mode=State("expansion_mode", "value"),
                  num_nodes_to_add=State("num_nodes_add", "value"),
                  add_edges_opt=State("add_edges", "value"),
              ))
def generate_elements(graph_active, graph_params, nodeData, focus, add_edge, focus_values, elements, expansion_mode,
                      num_nodes_to_add, add_edges_opt):
    """ This callback is responsible for generating the graph's elements, therefore
        it needs to respond to every input that can affect the graph - hence
        the huge amount of inputs.
    """
    if not graph_active:
        return []
    state = graph_params_to_state(graph_params)
    graph = state.graph

    ctx = dash.callback_context
    if not ctx.triggered:
        return []

    changed_inputs =set(
        prop['prop_id'].split('.')[0] for prop in ctx.triggered
    )
    tappedANode = any("cytoscape.tapNodeData" in prop['prop_id'] for prop in ctx.triggered)

    focus_node = "focus_button" in changed_inputs
    add_edge = "add_button" in changed_inputs
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
    elif add_edge:
        return add_nodes(state, elements, num_nodes_to_add, add_edges_opt)
    elif (not nodeData) or reload_graph:
        print("Graph is being reloaded")
        return [igraph_vert_to_cyto(graph, graph.vs[0], classes=["genesis"])]

    elif tappedANode:
        # tapped a node, try to expand
        if expansion_mode == "dont":
            return elements
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
        neigh_edges = get_filtered_edges(elements, (graph.es[ix]
                                         for ix in graph.incident(nodeData['id'], expansion_mode)))
        node_class, edge_class = "", ""
        if expansion_mode == "in":
            node_class, edge_class = "followerNode", "followerEdge"
        elif expansion_mode == "out":
            node_class, edge_class = "followingNode", "followingEdge"

        if do_expand:
            elements.extend(igraph_vert_to_cyto(graph, graph.vs[node_ix], classes=[node_class, "selneighbor"]) for node_ix in neigh_nodes)
            elements.extend(igraph_edge_to_cyto(graph, edge, classes=[edge_class, "selneighbor"])
                            for edge in neigh_edges)

        for element in elements:
            el_id = element.get('data').get('id')
            if el_id is None:
                continue
            if el_id not in neigh_names:
                element["classes"] = element["classes"].replace("selneighbor", "")
    return elements
    
