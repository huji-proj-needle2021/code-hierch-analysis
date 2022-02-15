from git_analysis.java_type import JavaFile, JavaClass, JavaMethod, JavaIdentifier, JavaHierarchy
from git_analysis.java_change import PosToJavaUnitMatcher

def test_pos_to_java_unit_matcher():
    tree = JavaFile(start=0, end=200, name="F", members=[])
    c1 = JavaClass(
            start=1, end=100, name="C1", kind="class", members=[], parent=tree)
    c1.members.extend([
        JavaMethod(start=5, end=40, name="C1M1", parent=c1),
        JavaMethod(start=41, end=80, name="C1M2", parent=c1)
    ])
    c2 = JavaClass(
            start=105, end=180, name="C2", kind="class", members=[], parent=tree)
    c2.members.extend([JavaMethod(start=110, end=140, name="C2M1", parent=c2),
                        JavaMethod(start=150, end=180, name="C2M2", parent=c2)
                        ])
    tree.members.extend([c1,c2])
    finder = PosToJavaUnitMatcher(tree)
    assert finder.find(0).name == "F"
    assert finder.find(1).name == "C1"
    assert finder.find(40).name == "C1"
    assert finder.find(41).name == "C1M2"
    assert finder.find(85).name == "C1"
    assert finder.find(100).name == "F"
    assert finder.find(120).name == "C2M1"
    assert finder.find(160).name == "C2M2"
    assert finder.find(180).name == "F"

    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 40)] == ["F", "C1", "C1M1"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 105)] == ["F", "C1", "C1M1", "C1M2"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 106)] == ["F", "C1", "C1M1", "C1M2", "C2"]
    finder = PosToJavaUnitMatcher(tree)
    assert [h.name for h in finder.find_range(0, 180)] == ["F", "C1", "C1M1", "C1M2", "C2", "C2M1", "C2M2"]