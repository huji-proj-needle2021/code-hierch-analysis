from git_analysis import GitProcessor
import logging
import pprint

def run():
    logging.basicConfig()
    logging.getLogger("git_processor").setLevel(logging.DEBUG)
    logging.getLogger("java_change_detector").setLevel(logging.DEBUG)
    pp = pprint.PrettyPrinter(indent=4)
    with GitProcessor("https://github.com/skylot/jadx") as git:
        prs = git.get_github_prs()
        git.process_pr(prs[0])
        pp.pprint(prs[0])


if __name__ == "__main__":
    run()