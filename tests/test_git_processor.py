from git_analysis.git_processor import git_repo_to_folder, git_repo_to_owner_and_repo

def test_repo_url():
    assert git_repo_to_folder("git@github.com:skylot/jadx.git") == "jadx"
    assert git_repo_to_owner_and_repo("git@github.com:skylot/jadx.git") == ("skylot", "jadx")
    assert git_repo_to_folder("https://github.com/skylot/jadx.git") == "jadx"
    assert git_repo_to_owner_and_repo("git@github.com:skylot/jadx.git") == ("skylot", "jadx")