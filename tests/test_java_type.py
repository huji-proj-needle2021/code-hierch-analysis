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

    f = JavaIdentifier.from_bottommost_hierarchy(tree)
    assert str(f) == "F"
    assert f.as_package() == f
    assert f.as_class() is None
    assert f.as_method() is None

    fc1 = JavaIdentifier.from_bottommost_hierarchy(c1)
    assert str(fc1) == "F.C1"
    assert fc1.as_class() == fc1
    assert fc1.as_method() is None
    assert str(fc1.as_package()) == "F"

    assert JavaIdentifier.from_bottommost_hierarchy(c1).identifier_type == HierarchyType.type_def
    c2m2 = JavaIdentifier.from_bottommost_hierarchy(c2.members[1])

    assert str(c2m2) == "F.C2.C2M2"
    assert c2m2.identifier_type == HierarchyType.method
    assert c2m2.as_method() == c2m2
    assert str(c2m2.as_class()) == "F.C2"
    assert str(c2m2.as_package()) == "F"