# %%
from __future__ import annotations
import subprocess
from git_analysis import HierarchyType
from typing import Any, Dict, NamedTuple, List
from pathlib import Path
import pandas as pd
import sys
import logging
import igraph
from dataclasses import dataclass


log = logging.getLogger("graph_import")

class RawGraph(NamedTuple):
    """ A raw representation of a directed graph as a frame of edges ('src' and 'tgt' columns)
        and a frame of node properties ('class', 'method', 'package' columns),
        can be easily (de)serialized to disk.
        
    """
    edges: pd.DataFrame
    node_props: pd.DataFrame

    @staticmethod
    def from_folder(folder: Path) -> RawGraph:
        edges_path = folder / "edges.json"
        node_map_path = folder / "mapping.json"
        edges = pd.read_json(edges_path, encoding='utf-8', orient="records")
        node_map = pd.read_json(node_map_path, encoding='utf-8', orient='index')
        cg = RawGraph(
            edges=edges,
            node_props=node_map
        )
        return cg

    def to_folder(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        self.edges.to_json(folder / "edges.json", orient="records")
        self.node_props.to_json(folder / "node_props.json", orient="index")

def raw_graph_to_igraph(raw: RawGraph, hierch: HierarchyType) -> igraph.Graph:
        edges = raw.edges[["src", "tgt"]]
        edges["weight"] = 1
        vertices = raw.node_props.reset_index()

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
            
            # at this point, the contracted graph(class/package) is likely
            # to include self-loops. These loops might be indicative of node importance,
            # e.g, a lot of activity or some kind of god class/package (in the callgraph model),
            # or something that changes very often(git diff model) so we may want to keep them.
            # We do combine parallel edges though, they just clutter the graph
            graph.simplify(multiple=True, loops=False, combine_edges="sum")

        # page rank for node importance
        graph.vs["pr"] = graph.pagerank(directed=True, weights="weight", damping=0.85,
                                        implementation="prpack")

        # TODO community detection for clustering

        return graph

def igraph_to_cytoscape_fig(graph: igraph.Graph, max_nodes: int, max_edges: int) -> List[Dict[str, Any]]:
    # first, pick up to 'max_nodes' with the highest importance
    vdf = graph.get_vertex_dataframe()
    vdf.sort_values(by="pr", ascending=False, inplace=True)

    inferred_hierch = None
    if "name" in vdf.columns:
        inferred_hierch = HierarchyType.method
    elif "class" in vdf.columns:
        inferred_hierch = HierarchyType.type_def
    else:
        inferred_hierch = HierarchyType.package

    chosen_ix = vdf[:max_nodes].index

    # now, delete edges with the lowest weights so we hav 
    # no more than 'max_edges' edges.
    subgraph = graph.induced_subgraph(chosen_ix)
    edf = subgraph.get_edge_dataframe()
    edf.sort_values(by="weight", ascending=True, inplace=True)
    n_edges_to_delete = max(len(edf) - max_edges, 0)
    subgraph.delete_edges(edf[:n_edges_to_delete].index)

    # converting to cytoscape element format
    def vertex_name(v):
        if inferred_hierch == HierarchyType.method:
            return v["name"]
        elif inferred_hierch == HierarchyType.type_def:
            return f"{v['package']}.{v['class']}"
        return v["package"]
    
    classes = inferred_hierch.name

    edges = [{'data': {'source': str(edge.source), 'target': str(edge.target)}}
             for edge in subgraph.es]
    nodes = [{'data': {'id': str(vertex.index), 'label': vertex_name(
        vertex), 'classes': classes}} for vertex in subgraph.vs]


    return edges + nodes


@dataclass
class Args:
    edge_filter: List[str]
    jar_filter: List[str]
    input_jar_folder: Path
    main_class_identifier: str
    graph_output_folder: Path

    def run_callgraph(self, genCallgraph_jar_path: Path, force_regen: bool = False) -> RawGraph:
        args = ["java", "-jar", str(genCallgraph_jar_path)]

        args.extend(["-i", str(self.input_jar_folder)])
        args.extend(["-m", self.main_class_identifier])
        args.extend(["-o", str(self.graph_output_folder)])

        if len(self.edge_filter) > 0:
            args.extend(["--edge-filter"] + self.edge_filter)
        if len(self.jar_filter) > 0:
            args.extend(["--jar-filter"] + self.jar_filter)
        
        edges_path = self.graph_output_folder / "edges.json"
        node_map_path = self.graph_output_folder / "mapping.json"

        if not edges_path.exists() or not node_map_path.exists() or force_regen:
            log.info("Generating callgraphs")
            ret = subprocess.call(args)
            if ret != 0:
                log.error(f"Generating callgraphs failed")
                sys.exit(ret)
        else:
            log.info(f"Using pre-existing graph files at {self.graph_output_folder}")
        
        edges = pd.read_json(edges_path, encoding='utf-8', orient="records")
        node_map = pd.read_json(node_map_path, encoding='utf-8', orient='index')

        cg = RawGraph(
            edges = edges,
            node_props= node_map
        )
        log.info(f"Call graph has {len(cg.node_props)} nodes and {len(cg.edges)} edges")
        return cg

GEN_CALLGRAPH_JAR = Path(__file__).resolve().parent / "genCallgraph.jar"
JAR_FOLDER = Path(__file__).resolve().parent.parent / "genCallgraph" / "toAnalyze"
OUTPUT_FOLDER = Path(__file__).resolve().parent / "graphImport"

def run(refresh=False):
    logging.basicConfig()
    log.setLevel(logging.DEBUG)
    args = Args(
        edge_filter=["jadx"],
        jar_filter=["jadx"],
        input_jar_folder=JAR_FOLDER,
        graph_output_folder=OUTPUT_FOLDER,
        main_class_identifier="jadx.gui.JadxGUI",
    )
    cg = args.run_callgraph(GEN_CALLGRAPH_JAR, force_regen=refresh)
    return cg


# %%
cg = run()
g = raw_graph_to_igraph(cg, HierarchyType.package)
# %%

if __name__ == "__main__":
    cg = run()
    print(cg.node_props)