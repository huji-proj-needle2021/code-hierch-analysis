import subprocess
from typing import NamedTuple, List
from pathlib import Path
import pandas as pd
import sys
import logging

log = logging.getLogger("graph_import")

class Callgraph(NamedTuple):
    edges: pd.DataFrame
    node_props: pd.DataFrame

class Args(NamedTuple):
    edge_filter: List[str]
    jar_filter: List[str]
    input_jar_folder: Path
    main_class_identifier: str
    graph_output_folder: Path

    def run_callgraph(self, genCallgraph_jar_path: Path, force_regen: bool = False) -> Callgraph:
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

        cg =  Callgraph(
            edges = edges,
            node_props= node_map
        )
        log.info(f"Call graph has {len(cg.node_props)} nodes and {len(cg.edges)} edges")
        return cg

GEN_CALLGRAPH_JAR = Path(__file__).resolve().parent.parent / "genCallgraph" / "target" / "genCallgraph-1.0-jar-with-dependencies.jar"
JAR_FOLDER = Path(__file__).resolve().parent.parent / "genCallgraph" / "toAnalyze"
OUTPUT_FOLDER = Path(__file__).resolve().parent / "graphImport"

if __name__ == "__main__":
    logging.basicConfig()
    log.setLevel(logging.DEBUG)
    args = Args(
        edge_filter=["jadx"],
        jar_filter=["jadx"],
        input_jar_folder=JAR_FOLDER,
        graph_output_folder=OUTPUT_FOLDER,
        main_class_identifier="jadx.gui.JadxGUI",
    )
    args.run_callgraph(GEN_CALLGRAPH_JAR)
