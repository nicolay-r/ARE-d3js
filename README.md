# ARE-d3js
![](https://img.shields.io/badge/Python-3.9-brightgreen.svg)

A [D3.js GUI](https://d3js.org/) for Information Retrieval and Visualization of Extracted Relations.

**Stack:**
* [Flask](https://flask.palletsprojects.com/en/stable/) -- web server
* [ARElight](https://github.com/nicolay-r/ARElight/tree/v0.25.1) -- AI / NLP backend 🤖
    * [nlp-thidgate](https://github.com/nicolay-r/nlp-thirdgate) -- providers for NLP components 📦️

<img width="1024" alt="interface" src="https://github.com/user-attachments/assets/552c78ae-5b49-4778-8070-10b913ebcf30" />

# Installation

Clone project and install dependencies:
```bash
pip install -r dependencies.txt
```

# Usage 

```bash
python3 server.py
```

You may follow the UI page at `http://127.0.0.1:8000/`

## Data Layout
```
noutput/
├── description/
    └── ...         // graph descriptions in JSON.
├── force/
    └── ...         // force graphs in JSON.
├── radial/
    └── ...         // radial graphs in JSON.
└── index.html      // main HTML demo page. 
```

# Graph Operations

For graph analysis you can perform several graph operations by this script:

1. Arguments mode:

```bash
python3 -m arelight.run.operations \
	--operation "<OPERATION-NAME>" \
	--graph_a_file output/force/boris.json \
  	--graph_b_file output/force/rishi.json \
  	--weights y \
  	-o output \
  	--description "[OPERATION] between Boris Johnson and Rishi Sunak on X/Twitter"
```

2. Interactive mode:

```bash
python3 -m arelight.run.operations
```

`arelight.run.operations` allows you to operate ARElight's outputs using graphs: you can merge graphs, find their similarities or differences.


<details>
<summary>

### Parameters

</summary>

* `--graph_a_file` and `--graph_b_file` are used to specify the paths to the `.json` files for graphs A and B, which are used in the operations.
  These files should be located in the `<your_output/force>` folder.
* `--name` -- name of the new graph.
* `--description` -- description of the new graph.
* `--host` -- determines the server port to host after the calculations.
* `-o` -- option allows you to specify the path to the folder where you want to store the output.
  You can either create a new output folder or use an existing one that has been created by ARElight.

</details>

<details>
<summary>

### Parameter `operation`
</summary>

#### Preparation

Consider that you used ARElight script for X/Twitter 
to [infer relations](#usage-inference) from
messages of UK politicians `Boris Johnson` and `Rishi Sunak`:

```bash
python3 -m arelight.run.infer ...other arguments... \
	-o output --collection-name "boris" --from-files "twitter_boris.txt"
	
python3 -m arelight.run.infer  ...other arguments... \
	-o output --collection-name "rishi" --from-files "twitter_rishi.txt"
```
According to the [results section](#layout-of-the-files-in-output), you will have `output` directory with 2 files `force` layout graphs:
```lua
output/
├── force/
    ├──  rishi.json
    └──  boris.json
```

#### List of Operations

You can do the following operations to combine several outputs, ot better understand similarities, and differences between them:

**UNION** $(G_1 \cup G_2)$ - combine multiple graphs together.
* The result graph contains all the vertices and edges that are in $G_1$ and $G_2$. 
The edge weight is given by $W_e = W_{e1} + W_{e2}$, and the vertex weight is its weighted degree centrality: $W_v = \sum_{e \in E_v} W_e(e)$.
  ```bash
  python3 -m arelight.run.operations --operation UNION \
      --graph_a_file output/force/boris.json \
      --graph_b_file output/force/rishi.json \
      --weights y -o output --name boris_UNION_rishi \
      --description "UNION of Boris Johnson and Rishi Sunak Twits"
  ```
  ![union](https://github.com/nicolay-r/ARElight/assets/14871187/eaac6758-69f7-4cc1-a631-7ce132757b29)

**INTERSECTION** $(G_1 \cap G_2)$ - what is similar between 2 graphs?
* The result graph contains only the vertices and edges common to $G_1$ and $G_2$. 
The edge weight is given by $W_e = \min(W_{e1},W_{e2})$, and the vertex weight is its weighted degree centrality: $W_v = \sum_{e \in E_v} W_e(e)$.
  ```bash
  python3 -m arelight.run.operations --operation INTERSECTION \
      --graph_a_file output/force/boris.json \
      --graph_b_file output/force/rishi.json \
      --weights y -o output --name boris_INTERSECTION_rishi \
      --description "INTERSECTION between Twits of Boris Johnson and Rishi Sunak"
  ```
  ![intersection](https://github.com/nicolay-r/ARElight/assets/14871187/286bd1ce-dbb0-4370-bfbe-245330ae6204)


**DIFFERENCE** $(G_1 - G_2)$ - what is unique in one graph, that another graph doesn't have? 

* **NOTE:** this operation is not commutative $(G_1 - G_2) ≠ G_2 - G_1)$)_
* The results graph contains all the vertices from $G_1$ but only includes edges from $E_1$ that either don't appear in $E_2$ or have larger weights in $G_1$ compared to $G_2$. 
The edge weight is given by $W_e = W_{e1} - W_{e2}$ if $e \in E_1$, $e \in E_1 \cap E_2$ and $W_{e1}(e) > W_{e2}(e)$.
  ```bash
  python3 -m arelight.run.operations --operation DIFFERENCE \
      --graph_a_file output/force/boris.json \
      --graph_b_file output/force/rishi.json \
      --weights y -o output --name boris_DIFFERENCE_rishi \
      --description "Difference between Twits of Boris Johnson and Rishi Sunak"
  ```
  ![difference](https://github.com/nicolay-r/ARElight/assets/14871187/8b036ce6-6607-4588-b0cf-4704647f55ff)

</details>

<details>
<summary>

### Parameter `weights`
</summary>

You have the option to specify whether to include edge weights in calculations or not. 
These weights represent the frequencies of discovered edges, indicating how often a relation between two instances was found in the text analyzed by ARElight.
* `--weights`
  * `y`: the result will be based on the union, intersection, or difference of these frequencies.
  * `n`: all weights of input graphs will be set to 1. In this case, the result will reflect the union, intersection, or difference of the graph topologies, regardless of the frequencies. This can be useful when the existence of relations is more important to you, and the number of times they appear in the text is not a significant factor.
  > Note that using or not using the `weights` option may yield different topologies:
  > 
  ![weights](https://github.com/nicolay-r/ARElight/assets/14871187/43ad2054-d413-47ee-ac8b-d06af6921214)

</details>