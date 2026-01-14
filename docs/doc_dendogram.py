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


if __name__ == "__main__":
    app.run()
