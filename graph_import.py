# %%

import subprocess
from git_analysis import HierarchyType
from typing import NamedTuple, List
from pathlib import Path
import pandas as pd
import sys
import logging
import igraph
from dataclasses import dataclass


log = logging.getLogger("graph_import")

class RawCallgraph(NamedTuple):
    edges: pd.DataFrame
    node_props: pd.DataFrame

    def to_python_graph(self, hierch: HierarchyType) -> igraph.Graph:
        # delete duplicate edges, we don't care if a method calls another
        # more than once

        edges = self.edges[["src", "tgt"]].drop_duplicates()
        edges["weight"] = 1
        vertices = self.node_props.reset_index()

        graph = igraph.Graph.DataFrame(edges, directed=True,
                                       vertices=vertices)

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
            graph.contract_vertices(mapping_vector, combine_attrs )



        return graph

@dataclass
class Args:
    edge_filter: List[str]
    jar_filter: List[str]
    input_jar_folder: Path
    main_class_identifier: str
    graph_output_folder: Path

    def run_callgraph(self, genCallgraph_jar_path: Path, force_regen: bool = False) -> RawCallgraph:
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

        cg = RawCallgraph(
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

if __name__ == "__main__":
    cg = run()
    print(cg.node_props)