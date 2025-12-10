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
