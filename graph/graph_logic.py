""" This module defines some graph functions that are used
    for exploring and visualizing a graph in the visualization
"""

from typing import List, Optional
import igraph
# from .app import cache
from .graph_data import GraphData
from git_analysis.java_type import HierarchyType
from pathlib import Path
import pandas as pd

def raw_graph_to_igraph(raw: GraphData, hierch: HierarchyType) -> igraph.Graph:

    assert int(hierch) <= int(raw.hierch), "cannot constrict a graph to a higher hierarchy"

    edges = raw.edges
    if "weight" in raw.edges.columns:
        edges["weight"] = raw.edges["weight"]
    else:
        edges["weight"] = 1
    vertices = raw.vertices.reset_index()

    print("converting raw to igraph",  hierch)
    graph = igraph.Graph.DataFrame(edges, directed=True,
                                    vertices=vertices)

    # Note: parallel edges/self loops not possible in association rule model
    # so this explanation is only relevant for call graph:
    #
    # We consider duplicate calls from one method to another, or self loops(recursive methods)
    # an implementation detail and not something that hints a stronger function depdenency, so
    # we remove them.
    graph.simplify(multiple=True, loops=True, combine_edges="first")
    contraction = {
        HierarchyType.method: None,
        HierarchyType.type_def: "class",
        HierarchyType.package: "package",
    }[hierch]
    if contraction:
        combine_attrs = {
            "package": "first"
        }
        if contraction == "class":
            combine_attrs["class"] = "first"
        mapping_vector, _ = pd.factorize(graph.vs[contraction], sort=False)
        graph.contract_vertices(mapping_vector, combine_attrs)

        # calculate a new "name" attribute
        if contraction == "class":
            graph.vs["name"] = pd.Series(graph.vs["package"]).apply(lambda s: s+".") + graph.vs["class"]
        else:
            graph.vs["name"] = graph.vs["package"]

        # at this point, the contracted graph(class/package) is likely
        # to include self-loops. These loops might be indicative of node importance,
        # e.g, a lot of activity or some kind of god class/package (in the callgraph model),
        # or something that changes very often(git diff model) so we may want to keep them.
        # We do combine parallel edges though, they just clutter the graph
        graph.simplify(multiple=True, loops=False, combine_edges="sum")

    # page rank for node importance
    graph.vs["pr"] = graph.pagerank(directed=True, weights="weight", damping=0.85,
                                    implementation="prpack")

    # graph.vs["community"] = graph.community_leiden(weights="weight")

    # TODO community detection for clustering
    return graph



def igraph_vert_to_cyto(g: igraph.Graph, vert: igraph.Vertex, classes: Optional[List[str]]=None):
    attrs = vert.attributes()
    data = { 
        **attrs,
        "id": attrs["name"],
        "label": attrs["name"]
    }
    return {
        "data": data,
        "classes": " ".join(classes or [])
    }

def igraph_edge_to_cyto(g: igraph.Graph, edge: igraph.Edge, classes: Optional[List[str]]=None):
    attrs = edge.attributes()
    return {
        "data": {
            **attrs,

            "source": g.vs[edge.source]["name"],
            "target": g.vs[edge.target]["name"],
        },
        "classes": " ".join(classes or [])
    }

def igraph_to_cyto(graph: igraph.Graph):
    return [
        igraph_vert_to_cyto(graph, vert) for vert in graph.vs
    ] + [
        igraph_edge_to_cyto(graph, edge) for edge in graph.es
    ]


def get_subgraph_by_pr_cyto(graph: igraph.Graph, max_nodes: int,
                            max_edges: int,
                            ascending_pr: bool = False,
                            ascending_weight: bool = False):
    """ Returns up to 'max_nodes' nodes and 'max_edges' edges,
        nodes sorted by page rank and edges by weight(both descending by default)
        The nodes and edges are returned in cytoscape format
    """

    # first, pick up to 'max_nodes' with the highest importance
    vdf = graph.get_vertex_dataframe()
    vdf.sort_values(by="pr", ascending=ascending_pr, inplace=True)
    chosen_ix = vdf[:max_nodes].index
    subgraph = graph.induced_subgraph(chosen_ix)

    # now, pick up to 'max_edges' edges with highest weights.
    # nodes with no edges will be removed
    edf = subgraph.get_edge_dataframe()
    edf.sort_values(by="weight", ascending=ascending_weight, inplace=True)
    subgraph = subgraph.subgraph_edges(edf[:max_edges].index, delete_vertices=True)

    return igraph_to_cyto(subgraph)
