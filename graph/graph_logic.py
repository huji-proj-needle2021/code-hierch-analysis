""" This module defines some functions for converting graph representations,
    from raw 'GraphData', to a pre-processed igraph representation,
    and utility methods for converting igraph objects to cytoscape.
"""

from typing import List, NamedTuple, Optional, Tuple, Union, Iterable
import igraph
# from .app import cache
from .graph_data import GraphData
from git_analysis.java_type import HierarchyType
from pathlib import Path
import pandas as pd

class ConversionArgs(NamedTuple):
    hierch: Union[HierarchyType, str]
    damping_factor: float = 0.85
    resolution: float = 1.0
    community_iters: int = 50


# https://stackoverflow.com/questions/470690/how-to-automatically-generate-n-distinct-colors
GRAPH_COLORS = [
    "#FFB300", # Vivid Yellow
    "#803E75", # Strong Purple
    "#FF6800", # Vivid Orange
    "#A6BDD7", # Very Light Blue
    "#C10020", # Vivid Red
    "#CEA262", # Grayish Yellow
    "#817066", # Medium Gray
    # The following don't work well for people with defective color vision
    "#007D34", # Vivid Green
    "#F6768E", # Strong Purplish Pink
    "#00538A", # Strong Blue
    "#FF7A5C", # Strong Yellowish Pink
    "#53377A", # Strong Violet
    "#FF8E00", # Vivid Orange Yellow
    "#B32851", # Strong Purplish Red
    "#F4C800", # Vivid Greenish Yellow
    "#7F180D", # Strong Reddish Brown
    "#93AA00", # Vivid Yellowish Green
    "#593315", # Deep Yellowish Brown
    "#F13A13", # Vivid Reddish Orange
    "#232C16", # Dark Olive Green
]

def raw_graph_to_igraph(raw: GraphData, args: ConversionArgs) -> Tuple[igraph.Graph, igraph.VertexClustering]:
    """ Converts a graph (whether a call graph or a graph from association rules)
        into igraph representation, optionally constricting the graph's hierarchy(combining nodes and edges
        with the same package/class)
        
        Calculates page rank values and assigns communities to nodes, to be used in visualization.
        Returns the igraph along with a 'VertexClustering' object that will allow us to explore specific
        communities
    """
    hierch = HierarchyType[args.hierch] if isinstance(args.hierch, str) else args.hierch 
    assert hierch in raw.hierch.included(), "cannot constrict a graph into a higher hierarchy than its own"

    edges = raw.edges
    if "weight" in raw.edges.columns:
        edges["weight"] = raw.edges["weight"]
    elif "confidence" in raw.edges.columns:
        edges["weight"] = raw.edges["confidence"]
    else:
        edges["weight"] = 1
    vertices = raw.vertices.reset_index()

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

        graph.simplify(multiple=True, loops=True, combine_edges={"weight": "sum"})

    # page rank for node importance
    graph.vs["pr"] = graph.pagerank(directed=True, weights="weight", damping=args.damping_factor,
                                    implementation="prpack")
    pr = pd.Series(graph.vs["pr"])
    norm_pr = (pr - pr.min()) / (pr.max() - pr.min())
    graph.vs["size"] = 16 + norm_pr * 30 

    undirected = graph.as_undirected(mode='collapse', combine_edges={'weight': 'sum'})
    clustering = undirected.community_leiden(n_iterations=args.community_iters,
                                             resolution_parameter=args.resolution, 
                                             objective_function='modularity',
                                             weights='weight')
    graph.vs["community"] = clustering.membership
    graph.vs["color"] = [GRAPH_COLORS[c % len(GRAPH_COLORS)] for c in clustering.membership]

    return graph, clustering



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