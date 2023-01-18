### Main steps for the creation of the html file

These are the main steps for the building of the html output file, generated with the command `renku aqs show-graph` (similar approach used for the `display` 
command, but the focus is now on the html-based one).

1. Extracting the graph from the working directory using the provided dedicated command, that returns a `Graph` object froom `rdflib`
2. Building the `CONSTRUCT` query, this includes two main parts:
    - _renku related_: information of inputs and outputs, time and commands for each run 
    - _astro related_: astroquery information intercepted by the plugin, specific to certain calls performed within our notebooks
3. Namespace binding: binding of the oda-specific prefixes to the namespace of the graph
4. Parsing the various configurations:
    - graphical ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_graphical_config.json)): 
    Nodes and Edges json file(s) graphical customization
    - reduction ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_reduction_config.json)): 
    certain nodes can "abosrb" child ones [example](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/readme_imgs/reduced_plan.png)
    - nodes subsets ([link](https://github.com/oda-hub/renku-aqs/blob/cli-display-graph/renkuaqs/graph_nodes_subset_config.json))
    to filter defined subset of nodes (eg astroquery-related nodes), uses the prefix 
5. Starting `Network` obj built using the pyvis library an html output is , and then a number of customizations are applied:
    - _head_ of the html file for the various javascript libraries:
      - Vis netowrk: draw nodes and edges, animations and various graphical customization
      - N3: parsing, writing and storing triples in several various formats
      - Comunica: for querying the graph
    - _javascript_: 
      - physics options for the graph
      - javascripts object for the various configurations are defined
    - _html content_:
      - buttons
      - checkboxes
      - legend
      - title
    
### Main functionalities provided by the javascript library

json files present also on the js library (for the github pages)