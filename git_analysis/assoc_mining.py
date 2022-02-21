from typing import Any, Mapping, Optional, Iterable, List
from .java_type import JavaIdentifier
from .java_change import HierarchyType, JavaChange
from mlxtend.frequent_patterns import apriori, fpgrowth, fpmax, association_rules
import logging
from tqdm import tqdm
import pandas as pd
import numpy as np
import networkx as nx

log = logging.getLogger("assoc_mining")

def convert_to_item_basket_onehot(commits_or_prs: Iterable[Mapping[str, Any]],
                                  hierarchy_type: HierarchyType,
                                  commit_or_pr: str) -> pd.DataFrame:
    """ Given an iterable of commits(for each commit-parent pair) or pull requests
        that were processed by GitProcessor, converts them to a Pandas dataframe
        with a one-hot encoding of the baskets, suitable for use by frequent itemsets
        algorithms.

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
    df = pd.DataFrame.from_records(records)
    df.set_index("basket_id", inplace=True)
    sparse_type = pd.SparseDtype(np.bool8, False)
    onehot = pd.get_dummies(df, prefix="", prefix_sep="")\
               .groupby(level=0).max()#.astype(sparse_type)
    
    log.info(f"item type: {hierarchy_type.name}, basket type: {commit_or_pr}, #baskets: {len(onehot)}, #items: {len(onehot.columns)}")

    return onehot
