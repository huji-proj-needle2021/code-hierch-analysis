from git_analysis import CommitProcessor
import pygit2
import itertools
import logging
import pprint

def run():
    logging.basicConfig()
    logging.getLogger("commit_processor").setLevel(logging.DEBUG)
    logging.getLogger("java_change_detector").setLevel(logging.DEBUG)
    print("running")
    ext = CommitProcessor("../testRepo")
    # add
    #ext.add_commit("26079d0b489702349a4cd71d5e960e502bf347a5")

    # modify function
    # ext.add_commit("6727b9ecd3cabf26d97a528afb284afcc4dccf12")

    # rename/delete class and add different class
    # ext.add_commit("786a4ce83e5652f37cbc0b5f7bd567e4968f5b58")
    
    # delete 
    ext.add_commit("a5cd45f1a193c8e85ecd770015bdffe3bd248425")


    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(ext.commits[0])



if __name__ == "__main__":
    run()