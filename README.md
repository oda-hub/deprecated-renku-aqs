# Collecting metadata with the plugin, inspecting it


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


![](subgraph.png)


## Sharing the metadata with the larger world

Pushing metadata to upstream, e.g. file:

```bash
$ renku aqs kg -u file:///tmp/rdf.ttl push
```

Or default SPARQL endpoint:

```bash
$ renku aqs kg push
```

Find suggestions for your workflow here:

```bash
$ renku aqs kg  suggest

+-------------------------------------------------------+----------------------------------------------+--------------------+
|                        Workflow                       |                 Astro Object                 |       Score        |
+-------------------------------------------------------+----------------------------------------------+--------------------+
| http://github.com/volodymyrss/renku-aqs-test-case.git | http://odahub.io/ontology#AstroObjectMrk_421 |        1.0         |
|                                                       |                  GRB211102B                  | 0.9192031027269952 |
|                                                       |                  GRB211102A                  | 0.9192031025575635 |
|                                                       |                    RS Oph                    |        1.0         |
|                                                       |                  FRB180916                   |        1.0         |
```