import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The goal of this document is to understand the "dendogram" part of the tool.

    A dendogram is a binary tree representing categories and sub-categories.

    All the functions related to this are in `./dendogram.py`

    In the script, we use the following terminology, illustrated by a diagram below:
    - *Tree*: the information about how groups are nested into each other.
    - *Opinion* or *Leaf* (<span style="color:lightgreen">green</span> in the diagram).
    - *Node* (<span style="color:gray">gray</span>  in the diagram): synonym for group. Each node has 2 children, either nodes or opinions.
    - *Regions* (<span style="color:#E2287B">red</span> in the diagram): special nodes that are chosen to partition all the opinions.
    - *Taxonomy* (ellipses in the diagram): Regions, and all the nodes above

    We then compute the mean and the deviation (variance times number of samples) for each node.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.mermaid("""
    graph LR
        0([Node 0]):::category
        1([Node 1]):::category

        subgraph region2["Subtree of region 2"]
        direction LR
            2([Node 2]):::region
            11[Opinion 1]:::opinion
            12[Opinion 2]:::opinion
            2 --> 11
            2 --> 12
        end

        subgraph region4["Subtree of region 3"]
        direction LR
            3([Node 3]):::region
            13[Opinion 3]:::opinion
            4[Node 4]
            17[Opinion 7]:::opinion
            18[Opinion 8]:::opinion
            3 --> 13
            3 --> 4
            4 --> 17
            4 --> 18
        end

        subgraph region3["Subtree of region 4"]
        direction LR
            5([Node 5]):::region
            6[Node 6]
            16[Opinion 6]:::opinion
            15[Opinion 5]:::opinion
            14[Opinion 4]:::opinion
            5 --> 16
            5 --> 6
            6 --> 15
            6 --> 14
        end

        0 --> 1
        0 --> 2
        1 --> 5
        1 --> 3

        classDef default fill:#808080,color:#000
        classDef region stroke:#C2185B,stroke-width:5px
        classDef opinion fill:#90EE90
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Sum Trees and Spread Calculation

    Our dendrogram has a **sum tree** structure for spread (variance) values. A sum tree is a binary tree where each node's value equals the sum of its children's values. In our case, the spread at each internal node is the sum of the spreads of its two children, while leaf nodes (opinions) have their individual spread values.

    ### Region Selection via Threshold

    To select regions, we use a spread threshold. A node becomes a **region** if:
    1. Its spread is **below** the threshold, AND
    2. Its parent's spread is **above** the threshold

    This creates a "frontier" that partitions the tree at an appropriate level of granularity.

    #### Example

    Let's say we have this tree:
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.mermaid("""
    graph TD
        A["A<br/>spread=100"]
        B["B<br/>spread=70"]
        C["C<br/>spread=30"]
        D["D<br/>spread=40"]
        E["E<br/>spread=30"]
        F[Opinion 1]:::opinion
        G[Opinion 2]:::opinion
        H[Opinion 3]:::opinion
        I[Opinion 4]:::opinion
        J[Opinion 5]:::opinion
        K[Opinion 6]:::opinion

        A --> B
        A --> C
        B --> D
        B --> E
        D --> F
        D --> G
        E --> H
        E --> I
        C --> J
        C --> K

        classDef opinion fill:#90EE90
        classDef default fill:#808080,color:#000
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We want to select a frontier of regions by applying a threshold. A node becomes a region if its spread is below the threshold while its parent's spread is above the threshold.

    With threshold = 50, we get the following regions:
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.mermaid("""
    graph TD
        A["A<br/>spread=100"]
        B["B<br/>spread=70"]
        C["C<br/>spread=30"]:::region
        D["D<br/>spread=40"]:::region
        E["E<br/>spread=30"]:::region
        F[Opinion 1]:::opinion
        G[Opinion 2]:::opinion
        H[Opinion 3]:::opinion
        I[Opinion 4]:::opinion
        J[Opinion 5]:::opinion
        K[Opinion 6]:::opinion

        A --> B
        A --> C
        B --> D
        B --> E
        D --> F
        D --> G
        E --> H
        E --> I
        C --> J
        C --> K

        classDef region stroke:#C2185B,stroke-width:5px,fill:#808080
        classDef opinion fill:#90EE90
        classDef default fill:#808080,color:#000
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Nodes **C**, **D**, and **E** are selected as regions (marked in red) because they're below the threshold while their parents are above.

    Result: Three regions partition all the leaves.
    """)
    return


if __name__ == "__main__":
    app.run()
