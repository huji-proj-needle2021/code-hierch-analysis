from git_analysis.java_type import JavaFile, JavaClass, JavaMethod, HierarchyType, JavaIdentifier

def test_dfs():
    tree = JavaFile(start=0, end=200, name="F", members=[])
    c1 = JavaClass(
            start=1, end=100, name="C1", members=[], parent=tree)
    c1.members.extend([
        JavaMethod(start=5, end=40, name="C1M1", parent=c1),
        JavaMethod(start=41, end=80, name="C1M2", parent=c1)
    ])
    c2 = JavaClass(
            start=105, end=180, name="C2", members=[], parent=tree)
    c2.members.extend([JavaMethod(start=110, end=140, name="C2M1", parent=c2),
                        JavaMethod(start=150, end=180, name="C2M2", parent=c2)
                        ])
    tree.members.extend([c1,c2])
    names = [h.name for h in tree.iterate_dfs_preorder()]
    assert names == ["F", "C1", "C1M1", "C1M2", "C2", "C2M1", "C2M2"]

    assert str(JavaIdentifier(c1)) == "F.C1"
    assert JavaIdentifier(c1).identifier_type == HierarchyType.type_def
    assert str(JavaIdentifier(c2.members[1])) == "F.C2.C2M2"
    assert JavaIdentifier(c2.members[1]).identifier_type == HierarchyType.method