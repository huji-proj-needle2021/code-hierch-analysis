from typing import Dict, Optional, Tuple, Any
import pygit2
from .java_change_detector import JavaChangeDetector, JavaIdentifier
from tqdm import tqdm
import logging
from pathlib import Path
from contextlib import AbstractContextManager
import re
import sys
import shelve
import requests
import json
from tqdm import tqdm

log = logging.getLogger("git_processor")

CONTEXT_LINES = 0

GIT_REPOS_FOLDER = Path(__file__).parent.parent / "GIT_REPOS"
SHELVE_PATH = Path(__file__).parent.parent / "GIT_REPOS_SHELVE"

def git_repo_to_folder(repo_url: str) -> str:
    return re.sub(r"\.git", "",  Path(repo_url).parts[-1])

def git_repo_to_owner_and_repo(repo_url: str) -> Tuple[str, str]:
    match = next(re.finditer(
        r"github.com[:/]([^/]+)/([^./]+)",
        repo_url
    ))
    return match.group(1), match.group(2)

def test_repo_url():
    assert git_repo_to_folder("git@github.com:skylot/jadx.git") == "jadx"
    assert git_repo_to_owner_and_repo("git@github.com:skylot/jadx.git") == ("skylot", "jadx")
    assert git_repo_to_folder("https://github.com/skylot/jadx.git") == "jadx"
    assert git_repo_to_owner_and_repo("git@github.com:skylot/jadx.git") == ("skylot", "jadx")

class GitProcessor(AbstractContextManager):
    """ Responsible for processing a git repository's commits and PRs, applying the Java
        diff change detection algorithm and storing it in a format usable for further Python
        analysis. 
    """
    def __init__(self, url: str, opt_path: Optional[str] = None):
        GIT_REPOS_FOLDER.mkdir(parents=True, exist_ok=True)
        if opt_path is None:
            folder_name = git_repo_to_folder(url)
            path = (GIT_REPOS_FOLDER / folder_name).resolve()
        else:
            path = Path(opt_path)
        
        if (path / ".git").exists():
            log.info(f"Using pre-existing git repository at {path}")
        elif path.exists():
            log.error(f"There exists a non-git path at {path}, please delete it or run the processor with a different path path")
            sys.exit(-1)
        else:
            log.info(f"Cloning repo at {url} into {path}")
            pygit2.clone_repository(url, str(path))
            log.info("Finished cloning")

        self.url = url
        self.path = path

        self.repo = pygit2.Repository(path)
        self.prs = []
        self.commits = []
        self.commits_by_id = {}
        self.change_detector = JavaChangeDetector(self.repo)

        log.info(f"Processing git repository located at {path}")
    
    def __enter__(self):
        self.shelve = shelve.open(str(self.path / "PYTHON_SHELF"))
        return self

    def __exit__(self, __exc_type, __exc_value, __traceback):
        self.shelve.close()
        return False

    def get_github_prs(self, refresh=False) -> Dict[str, Any]:
        prs = self.shelve.get("prs")
        if prs is None or refresh:
            log.info("Fetching PRs from Github API")
            prs = self._fetch_github_prs()
            self.shelve["prs"] = prs
        log.info(f"Got {len(prs)} pull requests")
        return prs

    def _fetch_github_prs(self) -> Dict[str, Any]:
        owner, repo = git_repo_to_owner_and_repo(self.url)
        pulls = []
        next_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        link_re = re.compile(r'<([^>]+)>;\s+rel="next"')
        while next_url is not None:
            log.info(f"Fetching PRs from Github API at {next_url}")
            r = requests.get(next_url, headers={
                "Accept": "application/vnd.github.v3+json"
            }, params={
                "state": "all"
            })
            r.raise_for_status()
            link = r.headers["Link"]
            next_url_match =  link_re.search(link)
            next_url = next_url_match.group(1) if next_url_match else None
            obj = json.loads(r.text)
            pulls.extend(obj)

        return pulls

    def add_all_commits(self):
        walk = self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL) 
        for commit in tqdm(walk):
            self.add_commit(commit)

    def process_all_prs(self):
        prs = self.get_github_prs()
        processed, unprocessed = [], []
        skipped = 0
        for pr in tqdm(prs, desc="Processing pull requests"):
            if pr.get("merged_at") is None:
                skipped += 1
                continue
            success = self.process_pr(pr)
            if success:
                processed.append(pr)
            else:
                unprocessed.append(pr)
        log.info(f"Processed {len(processed)} merged PRs, {len(unprocessed)} PRs failed to process, "
                 f"{skipped} rejected PRs were skipped.") 
        self.shelve["processed"] = processed
        self.shelve["unprocessed"] = unprocessed

    def process_pr(self, pr):
        log.debug(f'Processing PR #{pr["number"]} - "{pr["title"]}" ')
        if pr.get("merged_at") is None:
            log.debug(f"\tAttempted to process an unmerged PR, skipping")
            return False
        try:
            base_commit = self.repo.revparse_single(pr["base"]["sha"])
            merged_commit = self.repo.revparse_single(pr["merge_commit_sha"])
        except Exception as e:
            log.error(f"There was an obtaining the base/merged commit in PR #{pr['number']}: {e}")
            return False
        diff = self.repo.diff(base_commit, merged_commit, context_lines=CONTEXT_LINES)
        pr["parsed_patches"] = []
        for patch in diff:
            delta = patch.delta
            patch_object = {
                "from": delta.old_file.path, "to": delta.new_file.path,
                "status": delta.status_char(),
                "pr": pr["id"]
            }
            if patch_object["from"].endswith(".java") and patch_object["to"].endswith(".java"):
                log.debug(f'\tIdentifying Java changes in diff from "{patch_object["from"]}" to "{patch_object["to"]}" ')
                patch_object["changes"] = list(self.change_detector.identify_changes(patch))
            pr["parsed_patches"].append(patch_object)
        return True


    def add_commit(self, commit):
        if isinstance(commit, str):
            commit = self.repo.revparse_single(commit)
        commit_object = {
            "author": commit.author.email,
            "committer": commit.committer.email,
            "message": commit.message,
            "id": commit.id
        }
        self.commits.append(commit_object)
        self.commits_by_id[commit.id] = commit_object

        for parent in commit.parents:
            log.debug(f'Diffing commit {commit.id} - "{commit.message[:80].strip()}" with parent commit {parent.id} - "{parent.message[:80].strip()}"')
            diff = self.repo.diff(parent, commit, context_lines=CONTEXT_LINES)
            commit_object["patches"] = []
            for patch in diff:
                delta = patch.delta
                patch_object = {
                    "from": delta.old_file.path, "to": delta.new_file.path,
                    "status": delta.status_char(),
                    "parent_commit": parent.id,
                    "parent_commit_message": parent.message
                }
                if patch_object["from"].endswith(".java") and patch_object["to"].endswith(".java"):
                    log.debug(f'\tIdentifying Java changes in diff from "{patch_object["from"]}" to "{patch_object["to"]}" ')
                    patch_object["changes"] = list(self.change_detector.identify_changes(patch))
                commit_object["patches"].append(patch_object)

        
        