# %%
from git_analysis.git_processor import GitProcessor

from pathlib import Path
commits = []
cid = []

TEST_REPO_PATH = "C:\\dev\\testRepo"

def run():
    global commits, _
    with GitProcessor(url="https://github.com/huji-proj-needle2021/testRepo", opt_git_path=TEST_REPO_PATH) as git:
        commits, _ = git.get_processed_commits()

if __name__ == "__main__":
    run()
