from typing import Dict, Sequence

import numpy as np
import polars as pl
from polars import DataFrame


def dendogram_to_tree(dendogram) -> DataFrame:
    """
    converts a dendogram created from a hierarchical clustering
    to a binary tree, represented as a dataframe.
    Args:
        dendogram: hierarchy, as returned by `sklearn.cluster.AgglomerativeClustering()._children` for example

    Returns:
        Dataframe containing (id, id_parent) for each node.
        The dataframe also contains a "root" attribute.
        All nodes get the same root, but we used it because of the "cut_tree" function,
        which returns a forest with multiple roots.
    """
    n = len(dendogram) + 1
    parent = list(np.argsort(dendogram.ravel()) // 2 + n) + [None]
    return pl.DataFrame({"id": range(2 * n - 1), "parent": parent, "root": 2 * n - 2})


def child_count(tree: DataFrame) -> DataFrame:
    """
    count the number of children of each node in the tree.
    Returns:
        a DataFrame with attributes `id` and `child_count`
    """
    nodes = tree.select("id")
    return (
        nodes.join(tree, left_on="id", right_on="parent", how="left", suffix="_child")
        .group_by("id")
        .agg(pl.col("id_child").count().alias("child_count"))
    )


def compute_depth(tree: DataFrame) -> DataFrame:
    """
    compute the depth of each node in the tree.
    This must be a tree, and not a forest (one single root)
    Returns:
        a DataFrame with attributes `id` and `depth`
    """
    root = tree.filter(pl.col("parent").is_null()).select("id").item()
    children = tree.select("parent", "id").rows_by_key("parent")
    stack = [root]
    depth = {}
    depth[root] = 0
    while len(stack) > 0:
        x = stack.pop()
        for child in children.get(x) or []:
            c = child[0]
            depth[c] = depth[x] + 1
            stack.append(c)
    return tree.select(pl.col("id"), pl.col("id").replace(depth).alias("depth"))


def cut_tree(tree, new_roots) -> tuple[DataFrame, DataFrame]:
    """
    Given a tree and a set of nodes, remove all nodes from the tree.
    Args:
        tree: the tree to cut
        new_roots: the nodes to remove
    Returns:
        (trunk, subtrees) where:
            - trunk is the original tree with the strict descendents of `new_roots` removed
            - subtrees contains all the nodes that descend from `new_roots`.
                The "root" column will contain the new root for each node in the subtrees
    """
    children = tree.select("parent", "id").rows_by_key("parent")
    root = tree.filter(pl.col("parent").is_null())["id"].item()
    groups = {x: root for x in tree["id"]}
    parent = {x: p for (x, p) in tree.select("id", "parent").iter_rows()}
    nodes = []
    for r in new_roots:
        stack = [r]
        while len(stack) > 0:
            x = stack.pop()
            nodes.append(x)
            groups[x] = r
            for child in children.get(x) or []:
                c = child[0]
                stack.append(c)

    new_nodes = pl.DataFrame({"id": nodes})
    subtrees = new_nodes.select(
        id=pl.col("id"),
        root=pl.col("id").replace_strict(groups),
        parent=pl.col("id").replace_strict(parent, default=None),
    )
    trunk = tree.filter(
        pl.col("id")
        .replace_strict(parent, default=root)
        .replace_strict(
            groups, default=root
        )  # FIXME: why do we need the default value ?
        .eq(root)
    )
    return subtrees, trunk


def compute_hierarchy(tree) -> DataFrame:
    """
    compute all pairs of (node, ancestor) in the tree.

    Returns:
        a dataframe with columns "id" for the node and "ancestor"
    """
    nodes = tree["id"]
    children = tree.select("parent", "id").rows_by_key("parent")
    root = tree.filter(pl.col("parent").is_null())["id"].item()
    ancestors: Dict[int, Sequence[int]] = {x: tuple() for x in nodes}
    ancestors[root] = [root]
    stack = [root]
    while len(stack) > 0:
        node = stack.pop()
        for child in children[node]:
            c = child[0]
            ancestors[c] = [c] + list(ancestors[node])
            stack.append(c)
    return (
        nodes.to_frame()
        .select(
            pl.col("id"),
            pl.col("id")
            .replace_strict(ancestors, return_dtype=pl.List(pl.Int32))
            .alias("ancestor"),
        )
        .explode("ancestor", empty_as_null=False)
    )


def compute_layout(tree: DataFrame) -> DataFrame:
    """
    layout algorithm for a binary tree.
    Args:
        tree: the nodes to compute the position for
    Returns:
        a DataFrame with attributes `id`, `x` and `y`.
        The layout is computed left to right.
    """
    nodes = tree.select("id")
    children = tree.select("parent", "id").rows_by_key("parent")
    root = tree.filter(pl.col("parent").is_null())["id"].item()
    x = {}
    y = {}
    x[root] = 0
    stack = [root]
    previous_was_leaf = False
    v_y = 0.0
    while len(stack) > 0:
        node = stack.pop()
        if previous_was_leaf:
            v_y += 5 + 10 * (0.8 ** x[node])
        y[node] = v_y
        for child in children[node]:
            c = child[0]
            x[c] = x[node] + 1
            stack.append(c)
        if len(children[node]) == 0:
            previous_was_leaf = True
        else:
            previous_was_leaf = False
    return nodes.with_columns(
        x=pl.col("id").replace_strict(x), y=pl.col("id").replace_strict(y)
    )


def to_nested_dict(tree: DataFrame, info: DataFrame) -> dict:
    """
    Export the tree as a json-like representation, with nested dictionnaries.
    Args:
        tree: the nodes to export
        info: additional fields for each node, as a dataframe indexed by the "id" key.
    Returns:
        a dictionnary with fields:
        - id -> the root of the tree
        - a field for each column of `info`
        - children -> the list of children in the same format

    Exemple:
    ```py
    tree = pl.DataFrame(
        {"id": [1, 2, 3], "parent": [None, 1, 1]}
    )
    info = pl.DataFrame(
        {"id": [1, 2, 3], "custom_value": [0.1, 0.2, 0.3]}
    )
    to_nested_dict(tree, info)

    # Output:
    # {
    #   "custom_value": 0.1,
    #   "children": [
    #     {
    #       "custom_value": 0.2,
    #       "children": []
    #     },
    #     {
    #       "custom_value": 0.3,
    #       "children": []
    #     }
    #   ]
    # }
    ```
    """
    root = tree.filter(pl.col("parent").is_null())["id"].item()
    children = tree.select("parent", "id").rows_by_key("parent")
    id_to_dict = info.rows_by_key("id", unique=True, named=True)
    stack = [root]
    while len(stack) > 0:
        node = stack.pop()
        id_to_dict[node]["children"] = []
        for child in children[node]:
            c = child[0]
            id_to_dict[node]["children"].append(id_to_dict[c])
            stack.append(c)
    return id_to_dict[root]
