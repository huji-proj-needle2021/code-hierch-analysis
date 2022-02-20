# %%
from typing import Any, Mapping, Optional, Iterable, Union
from git_analysis import GitProcessor
from git_analysis.git_processor import ParsedPatch
from git_analysis.java_change import JavaChange, JavaIdentifier
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, fpgrowth, fpmax
import logging
import pprint
from tqdm import tqdm
import pandas as pd
import numpy as np

from git_analysis.java_type import HierarchyType


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

    records = []
    def change_to_desired_identifier(change: JavaChange) -> Optional[JavaIdentifier]:
        if hierarchy_type == HierarchyType.method:
            return change.identifier.as_method()
        if hierarchy_type == HierarchyType.type_def:
            return change.identifier.as_class()
        if hierarchy_type == HierarchyType.package:
            return change.identifier.as_package()
        

    index_col = "number" if commit_or_pr == "pr" else "id"
    for obj in commits_or_prs:
        for patch in obj["parsed_patches"]:
            patch: ParsedPatch
            changes = set(str(change_to_desired_identifier(change)) for change in patch.changes
                            if change_to_desired_identifier(change) is not None)
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
    
    return onehot

prs = []
pr_method_df: pd.DataFrame
pr_class_df: pd.DataFrame
pr_package_df: pd.DataFrame

commits = []
commit_method_df: pd.DataFrame
commit_class_df: pd.DataFrame
commit_package_df: pd.DataFrame


def run():
    global prs, pr_method_df, pr_class_df, pr_package_df
    global commits, commit_method_df, commit_class_df, commit_package_df
    logging.basicConfig()
    logging.getLogger("git_processor").setLevel(logging.INFO)
    logging.getLogger("java_change_detector").setLevel(logging.ERROR)
    with GitProcessor("https://github.com/skylot/jadx") as git:
        prs = git.get_processed_prs()
        commits, _ = git.get_processed_commits()

        pr_method_df = convert_to_item_basket_onehot(prs, HierarchyType.method, "pr")
        pr_class_df = convert_to_item_basket_onehot(prs, HierarchyType.type_def, "pr")
        pr_package_df = convert_to_item_basket_onehot(prs, HierarchyType.package, "pr")

        commit_method_df = convert_to_item_basket_onehot(commits, HierarchyType.method, "commit")
        commit_class_df = convert_to_item_basket_onehot(commits, HierarchyType.type_def, "commit")
        commit_package_df = convert_to_item_basket_onehot(commits, HierarchyType.package, "commit")

if __name__ == "__main__":
    run()

# %%
%%timeit

res = apriori(pr_method_df, min_support=0.033, use_colnames=True)
res

# %%
