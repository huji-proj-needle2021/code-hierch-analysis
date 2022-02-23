""" Based on https://raw.githubusercontent.com/plotly/dash-cytoscape/master/usage-elements.py
    modified to use our own graph
"""

import dash
from typing import Tuple
from dash import Input, Output, State, dcc, html

from git_analysis.java_type import HierarchyType
from graph.graph_logic import *
from .app import app, cache
from .graph_import import fetch_graph
import dash_cytoscape as cyto

import json

import dash_cytoscape as cyto
import viz.dash_reusable_components as drc
from pathlib import Path

from graph_import import *


# ###################### DATA PREPROCESSING ######################
# Load data
# with open(Path(__file__).parent / 'sample_network.txt', 'r') as f:
#     network_data = f.read().split('\n')

# # We select the first 750 edges and associated nodes for an easier visualization
# edges = network_data[:750]
# nodes = set()

# following_node_di = {}  # user id -> list of users they are following
# following_edges_di = {}  # user id -> list of cy edges starting from user id

# followers_node_di = {}  # user id -> list of followers (cy_node format)
# followers_edges_di = {}  # user id -> list of cy edges ending at user id

# cy_edges = []
# cy_nodes = []

# for edge in edges:
#     if " " not in edge:
#         continue

#     source, target = edge.split(" ")

#     cy_edge = {'data': {'id': source+target, 'source': source, 'target': target}}
#     cy_target = {"data": {"id": target, "label": "User #" + str(target[-5:])}}
#     cy_source = {"data": {"id": source, "label": "User #" + str(source[-5:])}}

#     if source not in nodes:
#         nodes.add(source)
#         cy_nodes.append(cy_source)
#     if target not in nodes:
#         nodes.add(target)
#         cy_nodes.append(cy_target)

#     # Process dictionary of following
#     if not following_node_di.get(source):
#         following_node_di[source] = []
#     if not following_edges_di.get(source):
#         following_edges_di[source] = []

#     following_node_di[source].append(cy_target)
#     following_edges_di[source].append(cy_edge)

#     # Process dictionary of followers
#     if not followers_node_di.get(target):
#         followers_node_di[target] = []
#     if not followers_edges_di.get(target):
#         followers_edges_di[target] = []

#     followers_node_di[target].append(cy_source)
#     followers_edges_di[target].append(cy_edge)

# genesis_node = cy_nodes[0]
# genesis_node['classes'] = "genesis"
# default_elements = [genesis_node]

default_stylesheet = [
    {
        "selector": 'node',
        'style': {
            "opacity": 0.65,
            'z-index': 9999
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
                    name='Expand',
                    id='radio-expand',
                    options=drc.DropdownOptionsList(
                        'followers',
                        'following'
                    ),
                    value='followers'
                )
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


@app.callback(Output('cytoscape', 'elements'),
              inputs=dict(
                  graph_active=Input("graph_active", "data"),
                #   graph_params=dict(
                #       import_dir=Input("import_dir", "value"),
                #       hierch=Input("hierch", "value"),
                #       resolution=Input("cd_resolution", "value"),
                #       community_iters=Input("cd_iter", "value"),
                #       damping_factor=Input("pr_damp", "value")
                #   ),
                  graph_params=Input("graph_params", "data"),
                  nodeData=Input("cytoscape", "tapNodeData")
              ),
              state=dict(
                  elements=State("cytoscape", "elements"),
                  expansion_mode=State("radio-expand", "value")
              ))
def generate_elements(graph_active, graph_params, nodeData, elements, expansion_mode):
    if not graph_active:
        return []
    import_dir = graph_params.pop("import_dir")
    args = ConversionArgs(**graph_params)
    graph, clustering = fetch_graph(import_dir, args)

    ctx = dash.callback_context
    if not ctx.triggered:
        return []

    reload_graph = any(
        prop['prop_id'].split('.')[0] in ("import_dir", "graph_params") for prop in ctx.triggered
    )

    if not nodeData or reload_graph:
        print("Graph is being reloaded")
        return [igraph_vert_to_cyto(graph, graph.vs[0], classes=["genesis"])]

    # If the node has already been expanded, we don't expand it again
    if nodeData.get(f'expanded-{expansion_mode}'):
        return elements

    # This retrieves the currently selected element, and tag it as expanded
    for element in elements:
        if nodeData['id'] == element.get('data').get('id'):
            element['data'][f'expanded-{expansion_mode}'] = True
            break
        
    dir = "in" if expansion_mode == "followers" else "out"
    neigh_nodes = graph.neighbors(nodeData['id'], dir)
    neigh_edges = graph.incident(nodeData['id'], dir)
    node_class = "followerNode" if dir == "in" else "followingNode"
    edge_class = "followerEdge" if dir == "in" else "followingEdge"



    elements.extend(igraph_vert_to_cyto(graph, graph.vs[node_ix], classes=[node_class]) for node_ix in neigh_nodes)
    elements.extend(igraph_edge_to_cyto(graph, graph.es[edge_ix], classes=[edge_class]) for edge_ix in neigh_edges)
    return elements
    

    # if expansion_mode == 'followers':
        
    #     followers_nodes = followers_node_di.get(nodeData['id'])
    #     followers_edges = followers_edges_di.get(nodeData['id'])

    #     if followers_nodes:
    #         for node in followers_nodes:
    #             node['classes'] = 'followerNode'
    #         elements.extend(followers_nodes)

    #     if followers_edges:
    #         for follower_edge in followers_edges:
    #             follower_edge['classes'] = 'followerEdge'
    #         elements.extend(followers_edges)

    # elif expansion_mode == 'following':

    #     following_nodes = following_node_di.get(nodeData['id'])
    #     following_edges = following_edges_di.get(nodeData['id'])

    #     if following_nodes:
    #         for node in following_nodes:
    #             if node['data']['id'] != genesis_node['data']['id']:
    #                 node['classes'] = 'followingNode'
    #                 elements.append(node)

    #     if following_edges:
    #         for follower_edge in following_edges:
    #             follower_edge['classes'] = 'followingEdge'
    #         elements.extend(following_edges)

    # return elements
