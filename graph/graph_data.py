from __future__ import annotations
import pandas as pd
from pathlib import Path
from typing import NamedTuple, Mapping, Any
from git_analysis.java_type import HierarchyType
import json

class GraphData(NamedTuple):
    """ An unprocessed graph of Java hierarchies, whether made from git analysis or
        a callgraph, including metadata about its creation.
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
