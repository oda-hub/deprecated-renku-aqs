## Two `cli` commands

- `display` to generate a representation of the graph over an output image file: still supported but not the main focus
- `show-graph` to start an interactive visualization of the graph over the browser: currently the main focus, parses the graph extracted from the current working folder, queries it and  outputs an html file opened then in the browser

### Main steps for the creation of the html file

1. Extracting the graph from the working directory using the provided dedicated command, that returns a `Graph` object froom `rdflib` and apply the binding to various namespaces
2. Building the `CONSTRUCT` query, this includes two main parts:
    - _renku related_: information of inputs and outputs, time and commands for each run/activity
    - _astro related_: astroquery information intercepted by the plugin, specific to certain calls performed within our notebooks and annoted using the plugin
3. Query the graph and build another `Graph` object that parses the data of the result of the query (and re-apply the oda-specific prefixes to the namespace of the graph, since those are nor preserved from the query result)
4. Parsing the various configurations, provided as json files within the plugin:
    - graphical ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_graphical_config.json)): 
    Nodes and Edges json file(s) graphical customization
    - reduction ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_reduction_config.json)): 
    certain nodes can "absorb" child ones [example](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/readme_imgs/reduced_plan.png), we specify a node and the relative edges it can absorb
    - nodes subsets ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_nodes_subset_config.json))
    to show or hide certain defined subset of nodes (eg astroquery-related nodes), uses the related prefixes
5. Using the `pyvis` library (a wrapper of javascript `vis.js` library), a `Network` obj is defined and the html template object is then generated, and then a number of customizations are applied:
    - _head_ of the html content for the various javascript libraries:
      - [N3](https://github.com/rdfjs/N3.js/): parsing, writing and storing triples in several various formats
      - [Comunica](https://github.com/rdfjs/comunica-browser): for querying the graph
      - [renku-aqs-graph-library](https://github.com/oda-hub/renku-aqs-graph-library/): javascript for the graph drawing and interaction and css for some minor graphical customization
    - _javascript_: 
      - physics options for the graph
      - javascripts object for the various configurations are defined
    - _html content_:
      - buttons
      - checkboxes
      - legend
      - title
6. Write the modified over the final output html file
    
### Main functionalities provided by the javascript library

- Load the configuration(s): load the configuration passed from the plugin
- Draw and configure the graph: using the `ttl` export representation of the result of the query, and querying the first (small) subset of nodes, and configure also the user-interaction behavior:
   - click of a node: **Perform a query starting from the clicked node**
   - dragging of a node: make the involved node draggable
   - stabilized of the graph: stop the animation (stop the graph from "floating around") 
- Functions to apply the changes of the various checkboxes and radio buttons

An example set of json files, html output and `ttl` exporo are also present, and are used by the github pages

### Actions

- SDSC developer team will check the rest of the js library
- Have a more generic part for the generaiton of the graph
- Read from the `ttl` file in the javascript library
- Document the configurations
- Extra information regarding a node visualized with hover or click -> UI expert to provide some insight
- make PR from Renku CLI




