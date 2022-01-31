## Is this a recommendation engine?

In a way, it is. But it could be better seen as engine using existing blocks to constucting new scientific activities (workflow plans) producing publications, selected for best fit in collective scientific story (publication history). See more details [here](analysis-motivation.md)!

## How is the Upstream Graph populated?

We want to use the knowledge base of our activies, described in a knowledge graph. It includes:

* Runs of renku, including metadata harvested with the plugin we developed
* Multi-messenger events, from GCNs, ATels, and other sources. See [high-level preview page](https://integral-observatory.github.io/).
* Workflows, their input parameter types and default values; when suitable - output parameter types:
  * Multi-messenger analysis workflows
  * Cross-Calibration Workflows for INTEGRAL/ISGRI: includes contributed data reduction and elaboration of a [variety of high-energy sources](https://share.streamlit.io/volodymyrss/streamlit-cc/app.py).

* Does every paper correspond to a deterministic workflow?
  * in principle, yes. Since every paper was produced in some, albeit unknown, way. We can always identify a recipe for a paper, but we do not always have the means to execute it.

We also plan to include:
* All MMODA requests
* "Standard" results from fresh INTEGRAL data (Quick Look Activities).
* OpenAIRE graph https://graph.openaire.eu/develop/
* ORKG https://www.orkg.org/orkg/data
* Workflows discovered in github (or other public locations), plenty of [options](https://github.com/search?q=astroquery+in%3Afile+extension%3Aipynb)
* re3data, e.g. http://doi.org/10.17616/R38P6F
* Other open graphs: dbpedia, wikidata, https://www.microsoft.com/en-us/research/project/academic/


## Sharing the metadata with the larger world

Pushing metadata to upstream, e.g. file:

```bash
$ renku aqs kg -u file:///tmp/rdf.ttl push
```

Or default SPARQL endpoint:

```bash
$ renku aqs kg push
```

## Find suggestions for your workflow


Ignoring "now" (i.e. not associating it to the focus node and hence using it in computing distances):


```
$ renku aqs kg suggest  --max-entries 100 --filter-input-value 421 --explain --ignore-now --plot

traced:
    oda:Focus                                             1.00000  http://odahub.io/ontology#Focus
    oda:relatedTo                                         0.00000  http://odahub.io/ontology#relatedTo
    <http://github.com/oda-hub/oda-sdss/>                 1.00000  http://github.com/oda-hub/oda-sdss/
    oda:has_runs_with_astro_object                        1.00000  http://odahub.io/ontology#has_runs_with_astro_object
    oda:AstroObjectMrk_421                                1.00000  http://odahub.io/ontology#AstroObjectMrk_421
    oda:has_input_source_name_inverse                     1.00000  http://odahub.io/ontology#has_input_source_name_inverse
    <http://github.com/oda-hub/oda-sdss//Plan>            1.00000  http://github.com/oda-hub/oda-sdss//Plan
trace distance: 6

total distance: 3.428571428571429
total distance: 3.428571428571429 http://odahub.io/ontology#AstroObjectMrk_421
+-------------------------------------+----------------------------------------------+--------------------+
|               Workflow              |                    Inputs                    |      Distance      |
+-------------------------------------+----------------------------------------------+--------------------+
| http://github.com/oda-hub/oda-sdss/ |     http://odahub.io/ontology#GRB210421C     | 3.7333333333333334 |
| http://github.com/oda-hub/oda-sdss/ |     http://odahub.io/ontology#GRB210421A     | 3.7333333333333334 |
| http://github.com/oda-hub/oda-sdss/ | http://odahub.io/ontology#AstroObjectMrk_421 | 3.428571428571429  |
+-------------------------------------+----------------------------------------------+--------------------+
```

![image](https://user-images.githubusercontent.com/3909535/141481430-f487319b-aca1-4ea2-b79a-a41923e5c530.png)




```bash

$ renku aqs kg suggest  --max-entries 100 --filter-input-value 421 --plot```

+-------------------------------------+----------------------------------------------+--------------------+
|               Workflow              |                    Inputs                    |      Distance      |
+-------------------------------------+----------------------------------------------+--------------------+
| http://github.com/oda-hub/oda-sdss/ | http://odahub.io/ontology#AstroObjectMrk_421 | 3.428571428571429  |
| http://github.com/oda-hub/oda-sdss/ |     http://odahub.io/ontology#GRB210421A     | 2.4317929154938036 |
| http://github.com/oda-hub/oda-sdss/ |     http://odahub.io/ontology#GRB210421C     | 2.431026469780614  |

```
![image](https://user-images.githubusercontent.com/3909535/141480299-6d50853a-f1e9-47ee-8134-aa9fb512cb23.png)


Notice how `Mrk 421` now less favorable. It is because GRBs are recent, and relate to current moment.




## Using IVOA Astro Object ontology

This example shows how object ontology connects sources which are related. Source names and workflows collected from cross-calibration test collection [ref](...).

![image](https://user-images.githubusercontent.com/3909535/141535619-e48808e6-2154-456e-962b-1f341ca574d9.png)

in cc-v0332

```bash
$ renku aqs kg suggest --filter-input-values '^(?!.*GRB20).*$' --max-options 1500 --learn-inputs --explain  --ignore-now
...
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git |     http://odahub.io/ontology#GRB210101A     | 12.68031496062992 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git |     http://odahub.io/ontology#GRB080102A     | 12.68031496062992 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git |     http://odahub.io/ontology#GRB080101A     | 12.68031496062992 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git | http://odahub.io/ontology#AstroObjectMrk_421 | 12.68031496062992 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git |    http://odahub.io/ontology/values#HerX1    |  7.38715063802749 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git |    http://odahub.io/ontology/values#CygX1    | 5.013123617596461 |
| http://gitlab.astro.unige.ch/integral/cc-workflows/cc-v0332.git | http://odahub.io/ontology/values#EXO0331530  | 4.421476510067114 |
+-----------------------------------------------------------------+----------------------------------------------+-------------------+
```


* EXO0331530 which is already used in the workflow - just a cross-check
* Cyg X-1 is the best new suggestion, since it's also an HXMB. 
* Her X-1 is an LXMB, so it shares a mid-level class (so, an additional long link) with Cyg X-1. 
* Still better than Mrk 421 which is an AGN.


It is possible to add specify interest in particular object class:

```bash
$ renku aqs kg suggest --filter-input-values -GRB2 --extra-focus http://www.ivoa.net/rdf/object-type#bl-lac
...
| http://renkulab.io/andrii.neronov/oda-benchmark.git |   source_name = Her X-1    | 3.2807881773399012 |
| http://renkulab.io/andrii.neronov/oda-benchmark.git | source_name = EXO 0331+530 | 3.2807881773399012 |
| http://renkulab.io/andrii.neronov/oda-benchmark.git |   source_name = Cyg X-1    | 3.2807881773399012 |
| http://renkulab.io/andrii.neronov/oda-benchmark.git |  source_name = GRB080101A  | 3.057648152884949  |
| http://renkulab.io/andrii.neronov/oda-benchmark.git |  source_name = GRB080102A  | 3.0576478882363274 |
| http://renkulab.io/andrii.neronov/oda-benchmark.git |    source_name = 3C 279    |        2.25        |
| http://renkulab.io/andrii.neronov/oda-benchmark.git |   source_name = Mrk 421    | 1.6517763713260378 |
+-----------------------------------------------------+----------------------------+--------------------+
```
![image](https://user-images.githubusercontent.com/3909535/142404255-48c35829-5f46-4a6b-8270-afcc1cf61faf.png)


Without extra focus, 3C 279 would be the best - in fact, it matches what was already used in this workflow. But with the focus - which is a BLLac, unlike 3C 279.


