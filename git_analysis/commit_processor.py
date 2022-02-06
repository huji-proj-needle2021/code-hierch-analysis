import pygit2
from .java_change_detector import JavaChangeDetector, JavaHierarchy
from tqdm import tqdm

class CommitProcessor:
    """ Responsible for processing git commits into a format usable by Python
        for further processing, includes inferring changes in the source code(Java)
    """
    def __init__(self, repo_path):
        self.repo = pygit2.Repository(repo_path)
        self.commits = []
        self.commits_by_id = {}
        self.change_detector = JavaChangeDetector()
    
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
            diff = self.repo.diff(commit, parent)
            commit_object["patches"] = []
            for patch in diff:
                delta = patch.delta
                patch_object = {
                    "from": delta.old_file.path, "to": delta.new_file.path,
                    "status": delta.status_char()
                }
                if patch_object["from"].endswith(".java") and patch_object["to"].endswith(".java"):
                    patch_object["changes"] = self.change_detector.identify_changes(self.repo, patch)
                commit_object["patches"].append(patch_object)

        
        