"""
Entry point to the 
"""

from genericpath import exists
from typing import Dict, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Any, Union
import pygit2

from git_analysis.java_change import JavaChange
from .java_change_detector import JavaChangeDetector
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
SHELVES_FOLDER = Path(__file__).parent.parent / "GIT_REPOS_SHELVE"

class ParsedPatch(NamedTuple):
    """ Represents changes to a .java file between two commits(e.g, a commit and its parent,
        or the base and merged commit of a pull request), and contains
        a set of JavaChanges identified after parsing both versions of the file.

        Usually, a commit or a PR will have many patches - one for each .java file added/removed/changed.
        Since a commit/PR is the "basket" in our associatino rules analysis, the items are the union of all
        changes(over all patches) for that commit/PR.
    """
    from_path: str
    to_path: str
    status_char: str
    changes: Set[JavaChange]

class GitProcessor(AbstractContextManager):
    """ Responsible for processing a git repository's commits and PRs, applying the Java
        diff change detection algorithm and caching the results using the 'shelve' module,
        so they can be later loaded quickly.
    """
    def __init__(self, url: str, opt_git_path: Optional[str] = None,
                 opt_shelve_path: Optional[str] = None):

        GIT_REPOS_FOLDER.mkdir(parents=True, exist_ok=True)
        SHELVES_FOLDER.mkdir(parents=True, exist_ok=True)

        # folder name used to identify analyzed project
        self.folder_name = git_repo_to_folder(url)
        self.url = url

        if opt_git_path is None:
            self.git_path = (GIT_REPOS_FOLDER / self.folder_name).resolve()
        else:
            self.git_path = Path(opt_git_path)
        
        if opt_shelve_path is None:
            self.shelve_path = (SHELVES_FOLDER / self.folder_name).resolve()
        else:
            self.shelve_path = Path(opt_shelve_path)
        

        if (self.git_path / ".git").exists():
            log.info(f"Using pre-existing git repository at {self.git_path}")
        elif self.git_path.exists():
            log.error(f"There exists a non-git path at {self.git_path}, please delete it or run the processor with a different path path")
            sys.exit(-1)
        else:
            log.info(f"Cloning repo at {url} into {self.git_path}")
            pygit2.clone_repository(url, str(self.git_path.resolve()))
            log.info("Finished cloning")

        if self.shelve_path.exists():
            log.info(f"Using pre-existing cache at {self.shelve_path}")
        else:
            self.shelve_path.mkdir(parents=True, exist_ok=True)
            log.info(f"Creating a cache at {self.shelve_path}")

        self.repo = pygit2.Repository(str(self.git_path.resolve()))
        self.change_detector = JavaChangeDetector(self.repo)

        log.info(f"Processing git repository located at {self.git_path}")
    
    def __enter__(self):
        self.shelve = shelve.open(str((self.shelve_path / self.folder_name).resolve()))
        return self

    def __exit__(self, __exc_type, __exc_value, __traceback):
        self.shelve.close()
        return False

    def get_processed_prs(self, refresh=False):
        """ On first run(or if refresh=True), fetches all pull requests via Github API,
            and then processes the .java files changed within each PR using the Java change detector.

            Returns a list of PR objects, each containing a list of `ParsedPatch` objects under
            'parsed_patches' field
        """
        if "processed" not in self.shelve or refresh:
            self._process_all_prs()
        return self.shelve["processed"]

    def get_processed_commits(self, refresh=False) -> Tuple[List[Any], Mapping[str, Any]]:
        """ On first run(or if refresh=True), traverses all commits in the git repository
            and then processes the .java files changed within each commit(between a commit and its parent)
            using the Java change detector.

            Returns a tuple containing:
            
            1. A list of commit-parent objects, each object containing a list of 'ParsedPatch' objects under
               'parsed_patches' field
            2. A map between commit IDs, to a list of commit-parent objects (the length of the list is
               the number of parents each commit has, usually 1 unless dealing with a merge commit)

               (both data structures contain)
        """
        if "processed_commits" not in self.shelve or refresh:
            self._process_all_commits()
        return self.shelve["processed_commits"], self.shelve["processed_commits_by_id"]

    def _get_github_prs(self, refresh=False) -> Dict[str, Any]:
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
            log.info(f"Fetching PRs from Github API at {next_url}, so far fetched {len(pulls)} PRs")
            r = requests.get(next_url, headers={
                "Accept": "application/vnd.github.v3+json"
            }, params={
                "state": "all",
                "per_page": "100"
            })
            r.raise_for_status()
            link = r.headers["Link"]
            next_url_match =  link_re.search(link)
            next_url = next_url_match.group(1) if next_url_match else None
            obj = json.loads(r.text)
            pulls.extend(obj)

        return pulls

    def _process_all_commits(self):
        count_walk = self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL) 
        log.debug("Counting number of commits in repo")
        count = sum(1 for _c in count_walk)
        log.debug(f"A total of {count} commits were detected")

        commits = []
        commits_by_id = {}

        walk = self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL) 
        for commit in tqdm(walk, total=count, desc="Processing commits"):
            for commit_object in self.process_commit(commit):
                commit_id = commit_object["id"]
                commits.append(commit_object)
                if commit_id not in commits_by_id:
                    commits_by_id[commit_id] = []
                commits_by_id[commit_id].append(commit_object)

        log.info(f"Processed a total of {len(commits)} parent-child commit pairs, "
                 f"or {len(commits_by_id)} commits")
        self.shelve["processed_commits"] = commits
        self.shelve["processed_commits_by_id"] = commits_by_id

    def _process_all_prs(self):
        prs = self._get_github_prs()
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


    def _parse_pygit_patch(self, pygit_patch) -> Optional[ParsedPatch]:
        """ Given a pygit2 patch, identifies all Java changes within that patch,
            and returns corresponding ParsedPatch object. Returns None if the file
            in the patch isn't a java file.
        """
        delta = pygit_patch.delta
        from_path = delta.old_file.path
        to_path = delta.new_file.path
        status_char = delta.status_char()
        if not from_path.endswith(".java") or not to_path.endswith("java"):
            return None
        log.debug(f'\tIdentifying Java changes in diff from "{from_path}"'
                  f'to "{to_path}". Status char: {status_char} ')
        return ParsedPatch(from_path=from_path,
                           to_path=to_path,
                           status_char=status_char,
                           changes=set(
                               self.change_detector.identify_changes(
                                   pygit_patch)
                           ))

    def process_pr(self, pr: Dict[str, Any]):
        """ Modifies the given pull request object in-place, adding
            a 'parsed_patches' field containing a list of parsed patch objects
        """
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
            parsed_patch = self._parse_pygit_patch(patch)
            if parsed_patch is not None:
                pr["parsed_patches"].append(parsed_patch)
        return True

    def process_commit(self, commit_or_hash: Union[Any, str]) -> Iterable[Mapping[str, Any]]:
        """ Given a commit identifier, returns commit objects (for each commit-parent pair, usually only
            1 commit is returned unless this is a merge commit)
            Each commit object contains a 'parsed_patches' field with a list of patches(file changes) between
            this commit and the corresponding parent.
        """

        commit = self.repo.revparse_single(commit_or_hash) if isinstance(commit_or_hash, str) else commit_or_hash
        template_commit_object = {
            "author": commit.author.email,
            "committer": commit.committer.email,
            "message": commit.message,
            "id": commit.id.raw
        }

        for parent in commit.parents:
            log.debug(f'Diffing commit {commit.id} - "{commit.message[:80].strip()}" with parent commit {parent.id} - "{parent.message[:80].strip()}"')
            commit_object = {**template_commit_object,
                "parent_author": parent.author.email,
                "parent_committer": parent.committer.email,
                "parent_message": parent.message,
                "parent_id": parent.id.raw,
                "parsed_patches": []
            }
            diff = self.repo.diff(parent, commit, context_lines=CONTEXT_LINES)
            commit_object["parsed_patches"] = []
            for patch in diff:
                parsed_patch = self._parse_pygit_patch(patch)
                if parsed_patch is not None:
                    commit_object["parsed_patches"].append(parsed_patch)
            
            yield commit_object


# misc utilities

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
