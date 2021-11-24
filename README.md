## Is this a recommendation engine?

In part it, it is. However, we try to recommend potentially long combinations of workflows, parameters. So the entities which are recommended need to be constructed, chained from individual, existing, pieces. In this sense, it is more similar to generation of human-readable sentences - except what we get is machine-executable sequences of steps (worklows).

Since we are parsing reported data and papers and generating new ones, we aim to produce a synthetic sequence of workflow executions: build the entire story of research community reaction to astrophysical events.

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


## Sources of ontology

TODO:
* runs of renku
* cc workflow
* MM INTEGRAL wfl
* Multi-messenger events
* "Standard" results from fresh INTEGRAL data (Quick Look Activities).
* OpenAIRE graph https://graph.openaire.eu/develop/

* mmoda requests
* astroquery in github (or other public locations), plenty of [options](https://github.com/search?q=astroquery+in%3Afile+extension%3Aipynb), let's leverage our committment  to astroquery, [see also](harvesting-public-sources.md)


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


