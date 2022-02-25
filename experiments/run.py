# %%
from typing import Any, Mapping, Optional, Iterable, Union
from git_analysis import GitProcessor
from git_analysis.git_processor import ParsedPatch
from git_analysis.java_change import JavaChange, JavaIdentifier
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, fpgrowth, fpmax, association_rules
import logging
import pprint
from tqdm import tqdm
import pandas as pd
import numpy as np
import networkx as nx


log = logging.getLogger("do analysis")

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
    
    print(f"hierch: {repr(hierarchy_type)}, basket type: {commit_or_pr}, #baskets: {len(onehot)}, #items: {len(onehot.columns)}")

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




# res = apriori(pr_method_df, min_support=0.033, use_colnames=True)
min_support = 14/len(commit_method_df)/2
print(f"With a min support of {min_support}, a change will have to appear in "
      f"{min_support*len(commit_method_df)} of {len(commit_method_df)} commits")
res = apriori(commit_method_df, min_support=min_support, use_colnames=True, max_len=2)
# res = apriori(commit_class_df, min_support=0.05, use_colnames=True)
print(f"Got {len(res)} itemsets.")

# %%

rules = association_rules(res, metric='confidence', min_threshold=0)
rules["weight"] = 1 - rules["confidence"]
rules["antecedents"] = rules["antecedents"].apply(lambda s: next(iter(s)))
rules["consequents"] = rules["consequents"].apply(lambda s: next(iter(s)))
print(f"Got {len(rules)} edges")
# rules["ant_len"] = rules["antecedents"].apply(len)
# rules["con_len"] = rules["consequents"].apply(len)

 # %%

graph = nx.convert_matrix.from_pandas_edgelist(rules, source="consequents", target="antecedents", edge_attr="weight")

# %%

nx.draw(graph)