""" A wrapper for generating callgraphs via 'genCallgraph.jar' in Python """
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
from graph.graph_data import GraphData, path_contains_graph
from graph.graph_logic import ConversionArgs


log = logging.getLogger("graph_import")

GRAPH_DIR = Path(__file__).parent / "GRAPHS"
GEN_CALLGRAPH_JAR = Path(__file__).resolve().parent / "genCallgraph.jar"

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
                raise ValueError("Generating callgraph failed, see log for details")
            
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
