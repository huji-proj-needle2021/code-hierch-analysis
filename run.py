# %%
from typing import Any, Mapping, Optional, Iterable, Union
from git_analysis import GitProcessor
from git_analysis.java_change import JavaChange, JavaIdentifier
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori
import logging
import pprint
from tqdm import tqdm
import pandas as pd
import numpy as np

from git_analysis.java_type import HierarchyType

prs = []
dfs: Mapping[str, pd.DataFrame] = {}

def processed_prs_to_onehot_changes(prs: Iterable[Mapping[str, Any]],
                                    hierarchy_type: HierarchyType) -> pd.DataFrame:
    """ Given an iterable of pull requests that were processed(via GitProcessor) to
        include Java changes (for each .java file changed in the pull request), 
        creates dataframes with one-hot representation of the changes in each pull request,
        using the changes(methods identifiers/class identifiers/package identifiers) as
        columns and the pull requests they occurred in as rows.
    """
    records = []
    def change_to_desired_identifier(change: JavaChange) -> Optional[JavaIdentifier]:
        if hierarchy_type == HierarchyType.method:
            return change.identifier.as_method()
        if hierarchy_type == HierarchyType.type_def:
            return change.identifier.as_class()
        if hierarchy_type == HierarchyType.package:
            return change.identifier.as_package()
        
    for pr in prs:
        num = pr["number"]
        for patch in pr["parsed_patches"]:
            changes = set(str(change_to_desired_identifier(change)) for change in patch.get("changes", [])
                            if change_to_desired_identifier(change) is not None)
            records.extend(({
                "pr": num,
                "change": change
            } for change in changes))
    df = pd.DataFrame.from_records(records)
    df.set_index("pr", inplace=True)
    onehot = pd.get_dummies(df, prefix="", prefix_sep="")\
               .groupby(level=0).max().astype(np.bool8)
    
    return onehot

method_df: pd.DataFrame
class_df: pd.DataFrame
package_df: pd.DataFrame

def run():
    global prs, method_df, class_df, package_df
    logging.basicConfig()
    logging.getLogger("git_processor").setLevel(logging.INFO)
    logging.getLogger("java_change_detector").setLevel(logging.ERROR)
    with GitProcessor("https://github.com/skylot/jadx") as git:
        prs = git.get_processed_prs()
        method_df = processed_prs_to_onehot_changes(prs, HierarchyType.method)
        class_df = processed_prs_to_onehot_changes(prs, HierarchyType.type_def)
        package_df = processed_prs_to_onehot_changes(prs, HierarchyType.package)

if __name__ == "__main__":
    run()

# %%


apriori(package_df, min_support=0.01, use_colnames=True)


# %%
