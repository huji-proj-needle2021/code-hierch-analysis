import pygit2
from .java_change_detector import JavaChangeDetector, JavaIdentifier
from tqdm import tqdm
import logging

log = logging.getLogger("commit_processor")

CONTEXT_LINES = 0

class CommitProcessor:
    """ Responsible for processing git commits into a format usable by Python
        for further processing, includes inferring changes in the source code(Java)
    """
    def __init__(self, repo_path):
        self.repo = pygit2.Repository(repo_path)
        self.commits = []
        self.commits_by_id = {}
        self.change_detector = JavaChangeDetector(self.repo)
    
    def add_all_commits(self):
        walk = self.repo.walk(self.repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL) 
        for commit in tqdm(walk):
            self.add_commit(commit)

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

        
        