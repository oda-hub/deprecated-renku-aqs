# renku-aqs

## `params`
```bash
$ (cd renku-aqs-test-case/; renku aqs params)
+--------------------------------------+-------------------+--------------+
| Run ID                               | AstroQuery Module | Astro Object |
+--------------------------------------+-------------------+--------------+
| 228555e4-151a-4440-919d-f1269132a0fb |    SimbadClass    |   Mrk 421    |
| 76943a72-30bf-4e9e-ad92-3dd068424968 |    SimbadClass    |   Mrk 421    |
| 0320ea0d-eee2-4b50-aa3e-b64c557b9bf2 |    SimbadClass    |   Mrk 421    |
+--------------------------------------+-------------------+--------------+
@prefix local-renku: <file:///home/savchenk/work/oda/renku/renku-aqs/renku-aqs-test-case/.renku/> .
@prefix oda: <http://odahub.io/ontology#> .
@prefix odas: <https://odahub.io/ontology#> .

local-renku:4ab60eb4-d5e7-11eb-a2dc-b5ff8b3b1162 a oda:Run ;
    oda:isRequestingAstroObject odas:AstroObjectMrk_421 ;
    oda:isUsing odas:AQModuleSimbadClass .

local-renku:53e67e80-d5ea-11eb-a2dc-b5ff8b3b1162 a oda:Run ;
    oda:isRequestingAstroObject odas:AstroObjectMrk_421 ;
    oda:isUsing odas:AQModuleSimbadClass .

local-renku:dd481450-d5e4-11eb-a2dc-b5ff8b3b1162 a oda:Run ;
    oda:isRequestingAstroObject odas:AstroObjectMrk_421 ;
    oda:isUsing odas:AQModuleSimbadClass .
  ```
![](readme_imgs/subgraph.png)

## `display` command

CLI command to generate an output graph and export it over an output image. 

Starting from the knowledge graph generated during the execution of a notebook,
this is queried to retrieve the needed information, perform some inferring and generate the output graph that will be finally
exported over an output picture.

In particular, the following information are elaborated:
* inputs/arguments/outputs of the notebook execution;
* [astroquery](https://github.com/oda-hub/astroquery/tree/DESILegacySurvey) modules used and the main query methods called ([astroquery api](https://github.com/astropy/astroquery/blob/main/docs/api.rst)).

### Parameters

* `--filename` The filename of the output file image, until now, only png images are supported (eg `--filename graph.png`), default is `graph.png`
* `--input-notebook` Input notebook to process, if not specified, will query for all the executions from all notebooks  
* `--no-oda-info` Exclude oda related information in the output graph, an output much closer to the lineage graph provided in the renkulab will be generated
```bash
$ (cd renku-aqs-test-case/; renku aqs display)
 ```
![](readme_imgs/example_display_graph_complete.png)

### Specify executed notebook
```bash
$ (cd renku-aqs-test-case/; renku aqs display --input-notebook final-an.ipynb)
 ```

![](readme_imgs/example_display_graph_final-an.png)

### Do not display oda-related information
```bash
$ (cd renku-aqs-test-case/; renku aqs display --input-notebook final-an.ipynb --no-oda-info)
 ```

![](readme_imgs/example_display_graph_final-an_no-oda-info.png)
