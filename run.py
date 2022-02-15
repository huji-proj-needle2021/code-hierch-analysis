from git_analysis import GitProcessor
import logging
import pprint
from tqdm import tqdm

def run():
    logging.basicConfig()
    logging.getLogger("git_processor").setLevel(logging.INFO)
    logging.getLogger("java_change_detector").setLevel(logging.ERROR)
    pp = pprint.PrettyPrinter(indent=4)
    with GitProcessor("https://github.com/skylot/jadx") as git:
        git.process_all_prs()

        


if __name__ == "__main__":
    run()