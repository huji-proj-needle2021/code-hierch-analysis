# %%
from __future__ import annotations
import subprocess
from git_analysis.java_type import HierarchyType
from typing import Any, Mapping, NamedTuple, List, Optional
from pathlib import Path
import pandas as pd
import sys
import logging
from dataclasses import dataclass
import json


log = logging.getLogger("graph_import")

GRAPH_DIR = Path(__file__).parent / "GRAPHS"

class GraphData(NamedTuple):
    """ An unprocessed graph of Java hierarchies, whether made from git analysis or
        a callgraph.
    """
    edges: pd.DataFrame
    vertices: pd.DataFrame

    hierch: HierarchyType

    # callgraph/git changes
    type: str

    # hash of the parameters, for caching
    hash: int

    # parameters used in generating the graph
    attrs: Mapping[str, Any]

    @staticmethod
    def from_folder(folder: Path) -> GraphData:
        edges_path = folder / "edges.json"
        node_map_path = folder / "mapping.json"
        meta_path = folder / "meta.json"

        edges = pd.read_json(edges_path, encoding='utf-8', orient="records")
        node_map = pd.read_json(node_map_path, encoding='utf-8', orient='index')
        with open(meta_path, 'r', encoding='utf-8') as meta_file:
            meta_obj = json.load(meta_file)
        cg = GraphData(
            edges=edges,
            vertices=node_map,
            hierch=HierarchyType[meta_obj["hierch"]],
            type=meta_obj["type"],
            hash=meta_obj["hash"],
            attrs=meta_obj["attrs"]
        )
        return cg

    def to_folder(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        edges_path = folder / "edges.json"
        node_map_path = folder / "mapping.json"
        meta_path = folder / "meta.json"

        self.edges.to_json(edges_path, orient="records")
        self.vertices.to_json(node_map_path, orient="index")

        with open(meta_path, 'w', encoding='utf-8') as meta_file:
            json.dump({
                "type": self.type,
                "hierch": self.hierch.name,
                "attrs": self.attrs,
                "hash": self.hash
            }, meta_file)




def path_contains_graph(path: Path) -> bool:
    return ((path / "edges.json").exists() and
            (path / "mapping.json").exists() and
            (path / "meta.json").exists())

@dataclass
class Args:
    edge_filter: List[str]
    jar_filter: List[str]
    input_jar_folder: Path
    main_class_identifier: str
    graph_output_folder: Path

    def run_callgraph(self, genCallgraph_jar_path: Path, force_regen: bool = False) -> GraphData:
        args = ["java", "-jar", str(genCallgraph_jar_path)]

        args.extend(["-i", str(self.input_jar_folder)])
        args.extend(["-m", self.main_class_identifier])
        args.extend(["-o", str(self.graph_output_folder)])

        if len(self.edge_filter) > 0:
            args.extend(["--edge-filter"] + self.edge_filter)
        if len(self.jar_filter) > 0:
            args.extend(["--jar-filter"] + self.jar_filter)
        
        if not path_contains_graph(self.graph_output_folder) or force_regen:
            log.info("Generating callgraphs")
            ret = subprocess.call(args)
            if ret != 0:
                log.error(f"Generating callgraphs failed")
                sys.exit(ret)
            
            # on success, generate metadata for caching purposes
            with open(self.graph_output_folder / "meta.json", 'w', encoding='utf-8') as meta:
                attrs = {**self.__dict__ }
                for k, v in attrs.items():
                    if isinstance(v, Path):
                        attrs[k] = str(v)
                hash_val = hash(json.dumps(attrs))
                json.dump({
                    "type": "callgraph",
                    "hierch": HierarchyType.method.name,
                    "attrs": attrs,
                    "hash": hash_val
                }, meta)
        else:
            log.info(f"Using pre-existing graph files at {self.graph_output_folder}")
        
        cg = GraphData.from_folder(self.graph_output_folder)
        log.info(f"{cg.type} has {len(cg.vertices)} nodes and {len(cg.edges)} edges")
        return cg

GEN_CALLGRAPH_JAR = Path(__file__).resolve().parent / "genCallgraph.jar"
JAR_FOLDER = Path(__file__).resolve().parent.parent / "genCallgraph" / "toAnalyze"
OUTPUT_FOLDER = GRAPH_DIR / "jadx"

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


if __name__ == "__main__":
    cg = run()
    print(cg.vertices)