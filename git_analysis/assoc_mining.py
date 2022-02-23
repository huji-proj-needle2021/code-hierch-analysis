from typing import Any, Dict, Mapping, NamedTuple, Optional, Iterable, List, Set, Tuple

from .git_processor import GitProcessor
from .java_type import JavaIdentifier
from .java_change import HierarchyType, JavaChange
from mlxtend.frequent_patterns import apriori, fpgrowth, fpmax, association_rules
import logging
from tqdm import tqdm
import pandas as pd
import numpy as np
from graph_import import GraphData
import json

log = logging.getLogger("assoc_mining")

def convert_to_item_basket_onehot(commits_or_prs: Iterable[Mapping[str, Any]],
                                  hierarchy_type: HierarchyType,
                                  commit_or_pr: str) -> Tuple[pd.DataFrame, Mapping[str, JavaIdentifier]]:
    """ Given an iterable of commits(for each commit-parent pair) or pull requests
        that were processed by GitProcessor, converts them to a Pandas dataframe
        with a one-hot encoding of the baskets, suitable for use by frequent itemsets
        algorithms. Also returns a mapping between columns(items) to their full JavaIdentifier objects

        Each row represents a basket - commit or PR
        Each column represents a possible item, there's one row for each Java Identifier in the program.
        (Note that we currently do not take the ChangeType into account - additions/deletions/modifies are treated
        the same)
    """

    records: List[Any] = []
    def change_to_desired_identifier(change: JavaChange) -> Optional[JavaIdentifier]:
        if hierarchy_type == HierarchyType.method:
            return change.identifier.as_method()
        if hierarchy_type == HierarchyType.type_def:
            return change.identifier.as_class()
        if hierarchy_type == HierarchyType.package:
            return change.identifier.as_package()
        raise ValueError("Impossible")

    index_col = "number" if commit_or_pr == "pr" else "id"
    for obj in commits_or_prs:
        changes = set(
            change_to_desired_identifier(change) for patch in obj["parsed_patches"]
            for change in patch.changes
            if change_to_desired_identifier(change) is not None
        )
        if len(changes) == 0:
            # skip if no .java files were changed
            continue
        records.extend(({
            "basket_id": obj[index_col],
            "item": change
        } for change in changes))

    str_to_iden = {
        str(rec["item"]): rec["item"] 
        for rec in records
    }

    df = pd.DataFrame.from_records(records)
    df.set_index("basket_id", inplace=True)
    sparse_type = pd.SparseDtype(np.bool8, False)
    onehot = pd.get_dummies(df, prefix="", prefix_sep="")\
               .groupby(level=0).max()#.astype(sparse_type)
    
    log.info(f"item type: {hierarchy_type.name}, basket type: {commit_or_pr}, #baskets: {len(onehot)}, #items: {len(onehot.columns)}")

    return onehot, str_to_iden


class ModelParams(NamedTuple):
    commit_or_pr: str
    hierarchy_type: HierarchyType
    min_support: float
    min_confidence: float

class Model(NamedTuple):
    """ An association rules model, along with all data used to
        create it.
    """
    params: ModelParams
    one_hot: pd.DataFrame
    col_mapping: Mapping[str, JavaIdentifier]
    freq_itemsets: pd.DataFrame
    assoc_rules: pd.DataFrame

    def describe(self) -> str:
        return (f"#baskets: {len(self.one_hot)} #items: {len(self.one_hot.columns)} "
                f"#freq itemsets: {len(self.freq_itemsets)} #rules: {len(self.assoc_rules)}")

def model_to_graph_data(model: Model) -> GraphData:
    pass

class AssocAnalyzer:
    """ Helper class for analyzing git changes via association rules.
        Mostly used to cache computations, 
    """

    def __init__(self, git_url: str):
        self._git_url = git_url
        with GitProcessor(git_url) as git:
            self._commits, _commits_by_id = git.get_processed_commits()
            self._prs = git.get_processed_prs()
        

        # caches to avoid re-calculating stuff
        self._onehots: Dict[Tuple[str, HierarchyType], Tuple[pd.DataFrame, Mapping[str, JavaIdentifier]]] = {}
        self._freq_itemsets: Dict[Tuple[str, HierarchyType, float], pd.DataFrame] = {}
        self._models: Dict[ModelParams, Model] = {}

    def _get_onehot(self, commit_or_pr: str, hierch_type: HierarchyType) -> Tuple[pd.DataFrame, Mapping[str, JavaIdentifier]]:
        """ Cached method for getting/creating an item-basket frame """
        assert commit_or_pr in ("commit", "pr")
        res = self._onehots.get((commit_or_pr, hierch_type), None)
        if res is None:
            collec = self._prs if commit_or_pr == "pr" else self._commits
            res = convert_to_item_basket_onehot(collec, hierch_type, commit_or_pr)
            self._onehots[(commit_or_pr, hierch_type)] = res
        return res
    
    def _get_freq_itemsets(self, commit_or_pr: str, hierch_type: HierarchyType, min_support: float) -> pd.DataFrame:
        """ Cached method for getting/creating  frequent itemsets frame """
        df = self._freq_itemsets.get((commit_or_pr, hierch_type, min_support), None)
        if df is None:
            one_hot, _ = self._get_onehot(commit_or_pr, hierch_type)
            df = apriori(one_hot, min_support=min_support,
                                    max_len=2, use_colnames=True, verbose=1)
            self._freq_itemsets[(commit_or_pr, hierch_type, min_support)] = df
        return df


    def analyze_model(self, model_params: Optional[ModelParams] = None, **kwargs) -> Model:
        """ Cached method for getting/creating association rules using the given model
            parameters
        """
        if model_params is None:
            model_params = ModelParams(**kwargs)
        
        model = self._models.get(model_params, None)
        if model:
            return model

        one_hot, mapping = self._get_onehot(model_params.commit_or_pr, model_params.hierarchy_type)
        freq_itemsets = self._get_freq_itemsets(model_params.commit_or_pr, model_params.hierarchy_type, 
                                                model_params.min_support)
        rules = association_rules(freq_itemsets, metric='confidence', min_threshold=model_params.min_confidence)
        rules["antecedents"] = rules["antecedents"].apply(lambda s: next(iter(s)))
        rules["consequents"] = rules["consequents"].apply(lambda s: next(iter(s)))

        model = Model(
            params=model_params,
            one_hot=one_hot,
            col_mapping=mapping,
            freq_itemsets=freq_itemsets,
            assoc_rules=rules
        )
        self._models[model_params] = model
        return model

    def create_graph(self, model: Model) -> GraphData:
        """ Creates a graph using associatino rules model,
            the graph might be persisted to disk or further analyzed.
        """
        model.assoc_rules["weight"] = model.assoc_rules["confidence"]
        edges = model.assoc_rules


        seenVertices: Set[str] = set()
        vertex_records = []
        for row in model.assoc_rules[["antecedents", "consequents"]].itertuples():
            nodes = set((row.consequents, row.antecedents)) - seenVertices
            seenVertices.update(nodes)
            for node in nodes:
                iden = model.col_mapping[node]
                record = {
                    "identifier": node
                }
                if model.params.hierarchy_type == HierarchyType.method:
                    record["method"] = iden.hierarchies[0][1]
                    record["class"] = ".".join(h[1] for h in iden.hierarchies[1:-1])
                    record["package"] = iden.hierarchies[-1][1]
                elif model.params.hierarchy_type == HierarchyType.type_def:
                    record["class"] = ".".join(h[1] for h in iden.hierarchies[:-1])
                    record["package"] = iden.hierarchies[-1][1]
                else:
                    record["package"] = iden.hierarchies[0][1]
                vertex_records.append(record)
            
        vertices = pd.DataFrame.from_records(vertex_records, index="identifier")

        

        attrs = {
            "git_url": self._git_url,
            **model.params._asdict()
        } 
        hash_val = hash(json.dumps(attrs))
        return GraphData(
            vertices=vertices,
            edges=edges,
            hierch=model.params.hierarchy_type,
            type="git_changes",
            attrs=attrs,
            hash=hash_val
        )
