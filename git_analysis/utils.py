import re
import heapq
import operator
from typing import Iterable, Tuple, Iterator, List


def finditer_with_line_numbers(pattern: re.Pattern, string: str, flags=0) -> Iterable[Tuple[re.Match, int]]:
    """
    A version of 're.finditer' that returns '(match, line_number)' pairs.
    Taken from https://stackoverflow.com/a/45142535
    """
    import re

    matches = list(re.finditer(pattern, string, flags))
    if not matches:
        return []

    end = matches[-1].start()
    # -1 so a failed 'rfind' maps to the first line.
    newline_table = {-1: 0}
    for i, m in enumerate(re.finditer(r'\n', string), 1):
        # don't find newlines past our last match
        offset = m.start()
        if offset > end:
            break
        newline_table[offset] = i

    # Failing to find the newline is OK, -1 maps to 0.
    for m in matches:
        newline_offset = string.rfind('\n', 0, m.start())
        line_number = newline_table[newline_offset]
        yield (m, line_number)


def iterate_regex_matches_sequentially(iters: List[Iterator[re.Match]]) -> Iterable[Tuple[int, re.Match]]:
    """ Given several iterators of Regex matches, returns a combined iterator over these matches
        sorted by match start positions, tupled with the index into the iterators list from which the match came from.

        Note that this mutates the iterators in 'iters'
    """

    current_matches = [
        (it_index, match) for it_index, match in
        enumerate(next(iter, None) for iter in iters)
        if match
    ]
    while len(current_matches) > 0:
        print(current_matches)
        current_matches_ix = min(
            range(len(current_matches)), key=lambda i: current_matches[i][1].start())

        it_index, min_match = current_matches[current_matches_ix]

        yield it_index, min_match
        next_match = next(iters[it_index], None)
        if next_match is not None:
            current_matches[current_matches_ix] = it_index, next_match
        else:
            current_matches.pop(current_matches_ix)

def test_iterate_regex_matches_sequentially():
    pat_1 = re.compile(r"A (\d)+")
    pat_2 = re.compile(r"B (\d)+")
    text = """
    A 1 
    B 2
    B 3 
    A 4
    B 5
    """

    iters = [pat.finditer(text) for pat in (pat_1, pat_2)]
    results = list(iterate_regex_matches_sequentially(iters))
    assert len(results) == 5
    assert [(it_ix, int(match.group(1))) for it_ix, match in results] == [ (0, 1), (1, 2), (1, 3), (0, 4), (1, 5)]


    # edge cases
    text2 = """
    """

    iters_2 = [pat.finditer(text2) for pat in (pat_1, pat_2)]
    results_2 = list(iterate_regex_matches_sequentially(iters_2))
    assert len(results_2) == 0

    text3 = """
    A 1
    """
    iters_3 = [pat.finditer(text3) for pat in (pat_1, pat_2)]
    results_3 = list(iterate_regex_matches_sequentially(iters_3))
    assert [(it_ix, int(match.group(1))) for it_ix, match in results_3] == [ (0, 1)]


def test_finditer_with_linenumbers():
    pat = re.compile(r"\s*LINE (\d+)")
    text = """LINE 0
    LINE 1
    LINE 2
    LINE 3
    test
    LINE 5"""

    n_matches = 0
    for (match, gotten_line) in finditer_with_line_numbers(pat, text):
        assert int(match.group(1)) == gotten_line
        n_matches += 1
    assert n_matches == 5

    text2 = """notMatch
    notMatchEither
    LINE 2
    """

    for (match, gotten_line) in finditer_with_line_numbers(pat, text2):
        assert int(match.group(1)) == gotten_line

    multiline_pat = re.compile(r"^LINE (\d+)\s*next", re.MULTILINE)
