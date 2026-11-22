# ARE-d3js
![](https://img.shields.io/badge/Python-3.9-brightgreen.svg)

A [D3.js GUI](https://d3js.org/) for Information Retrieval and Visualization of Extracted Relations.

**Stack:**
* [FastAPI](https://fastapi.tiangolo.com/) -- web server
* [ARElight](https://github.com/nicolay-r/ARElight/tree/v0.26.1) -- AI / NLP backend 🤖
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

Open the **operate** panel in the UI. It runs `D3jsGraphOperationsBackendPipelineItem` on graphs already written by the inference pipeline (`output/force/*.json`). You can merge graphs, or keep only what they share or what is unique to one of them.


Pick dataset A, an operation, and dataset B, then name the result. The new force and radial graphs are written next to the inputs.

**UNION** $(G_1 \cup G_2)$ keeps every vertex and edge from both graphs. Edge weight is $W_e = W_{e1} + W_{e2}$.

![union](https://github.com/nicolay-r/ARElight/assets/14871187/eaac6758-69f7-4cc1-a631-7ce132757b29)

**INTERSECTION** $(G_1 \cap G_2)$ keeps vertices and edges present in both graphs. Edge weight is $W_e = \min(W_{e1}, W_{e2})$.

![intersection](https://github.com/nicolay-r/ARElight/assets/14871187/286bd1ce-dbb0-4370-bfbe-245330ae6204)

**DIFFERENCE** $(G_1 - G_2)$ keeps vertices from $G_1$ and edges that are missing from $G_2$ or heavier in $G_1$. This operation is not commutative.

![difference](https://github.com/nicolay-r/ARElight/assets/14871187/8b036ce6-6607-4588-b0cf-4704647f55ff)

<details>
<summary>

### Parameter `weights`
</summary>

Edge weights are the number of times a relation was found. The UI keeps those weights. A weight of 1 for every edge would compare topology only.
  > Note that using or not using the `weights` option may yield different topologies:
  > 
  ![weights](https://github.com/nicolay-r/ARElight/assets/14871187/43ad2054-d413-47ee-ac8b-d06af6921214)

</details>