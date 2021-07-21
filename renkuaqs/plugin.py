# -*- coding: utf-8 -*-
#
# Copyright 2020 - Viktor Gal
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pathlib
import re
import sys
import json
import click
import rdflib
import rdflib.tools.rdf2dot
from copy import deepcopy
from pathlib import Path

from rdflib.tools import rdf2dot
from renku.core.models.cwl.annotation import Annotation
from renku.core.incubation.command import Command
from renku.core.plugins import hookimpl
from renku.core.models.provenance.provenance_graph import ProvenanceGraph
from renku.core.errors import RenkuException
from renku.core.management import LocalClient

from prettytable import PrettyTable

#from aqsconverters.models import Run
from aqsconverters.io import AQS_DIR, COMMON_DIR


class AQS(object):
    def __init__(self, run):
        self.run = run

    @property
    def renku_aqs_path(self):
        """Return a ``Path`` instance of Renku AQS metadata folder."""        
        return Path(self.run.client.renku_home).joinpath(AQS_DIR).joinpath(COMMON_DIR)

    def load_model(self, path):
        """Load AQS reference file."""
        if path and path.exists():
            return json.load(path.open())
        return {}


@hookimpl
def process_run_annotations(run):
    """``process_run_annotations`` hook implementation."""
    aqs = AQS(run)

    #os.remove(os.path.join(aqs.renku_aqs_path, "site.py"))

    path = pathlib.Path("../sitecustomize.py")
    if path.exists():
        path.unlink()
    
    annotations = []

    print("process_run_annotations")

    if os.path.exists(aqs.renku_aqs_path):
        for p in aqs.renku_aqs_path.iterdir():
            if p.match("*json"):
                print(f"found json annotation: {p}")
                print(open(p).read())
        
            elif p.match("*jsonld"):
                print(f"found jsonLD annotation: {p}\n", json.dumps(json.load(p.open()), sort_keys=True, indent=4))
                

                # this will make annotations according to https://odahub.io/ontology/
                aqs_annotation = aqs.load_model(p)
                model_id = aqs_annotation["@id"]
                annotation_id = "{activity}/annotations/aqs/{id}".format(
                    activity=run._id, id=model_id
                )
                p.unlink()
                annotations.append(
                    Annotation(id=annotation_id, source="AQS plugin", body=aqs_annotation)
                )
    else:
        print("nothing to process in process_run_annotations")

    return annotations

@hookimpl
def pre_run(tool):
    # we print
    print(f"\033[31mhere we will prepare hooks for astroquery, tool given is {tool}\033[0m")    

    # TODO: where to get renku.client and dir?

    # TODO: how to write provide this to `tool`?
    fn = "../sitecustomize.py"

    print(f"\033[34msitecustomize.py as {fn}\033[0m")    

    open(fn, "w").write("""
print(f"\033[31menabling hooks for astroquery\033[0m")  

import aqsconverters.aq

aqsconverters.aq.autolog()
""")

    from astroquery.query import BaseQuery # ??

def _run_id(activity_id):
    return str(activity_id).split("/")[-1]


def _load_provenance_graph(client):
    if not client.provenance_graph_path.exists():
        raise RenkuException(
            """Provenance graph has not been generated!
Please run 'renku graph generate' to create the project's provenance graph
"""
        )
    return ProvenanceGraph.from_json(client.provenance_graph_path)


def _graph(revision, paths):
    # FIXME: use (revision, paths) filter
    cmd_result = Command().command(_load_provenance_graph).build().execute()

    provenance_graph = cmd_result.output
    provenance_graph.custom_bindings = {
        "aqs": "http://www.w3.org/ns/aqs#",
        "oa": "http://www.w3.org/ns/oa#",
        "xsd": "http://www.w3.org/2001/XAQSchema#",
    }

    return provenance_graph


def renku_context():
    ctx = click.get_current_context().ensure_object(LocalClient)
    return ctx


def _create_leaderboard(data, metric, format=None):
    leaderboard = PrettyTable()
    leaderboard.field_names = ["Run ID", "Module", "Query", metric]
    leaderboard.align["Module"] = "l"
    leaderboard.align["Query"] = "l"
    leaderboard.align[metric] = "r"
    for commit, v in data.items():
        if metric in v:
            v["query"].sort()
            leaderboard.add_row([commit, v["module"], v["query"], v[metric]])
    leaderboard.sortby = metric
    leaderboard.reversesort = True
    return leaderboard


@click.group()
def aqs():
    pass


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--format", default="ascii", help="Choose an output format.")
@click.option("--metric", default="accuracy", help="Choose metric for the leaderboard")
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def leaderboard(revision, format, metric, paths):
    """Leaderboard based on performance of astroquery requests"""
    graph = _graph(revision, paths)
    leaderboard = dict()

    # how to use ontology
    for r in graph.query(
        """SELECT DISTINCT ?a_object ?aq_module WHERE {{
        ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object;
             <http://odahub.io/ontology#isUsing> ?aq_module .
        }}"""):

        print(r)
    # for r in graph.query(
    #     """SELECT DISTINCT ?type ?value ?run ?runId ?dsPath where {{
    #     ?em a aqs:ModelEvaluation ;
    #     aqs:hasValue ?value ;
    #     aqs:specifiedBy ?type ;
    #     ^aqs:hasOutput/aqs:implements/rdfs:label ?run ;
    #     ^aqs:hasOutput/^oa:hasBody/oa:hasTarget ?runId ;
    #     ^aqs:hasOutput/^oa:hasBody/oa:hasTarget/prov:qualifiedUsage/prov:entity/prov:atLocation ?dsPath
    #     }}"""
    #     run_id = _run_id(r.runId)
    #     metric_type = r.type.split("#")[1]
    #     if run_id in leaderboard:
    #         leaderboard[run_id]["inputs"].append(r.dsPath.__str__())
    #         continue
    #     leaderboard[run_id] = {
    #         metric_type: r.value.value,
    #         "model": r.run,
    #         "inputs": [r.dsPath.__str__()],
    #     }
    # if len(paths):
    #     filtered_board = dict()
    #     for path in paths:
    #         filtered_board.update(
    #             dict(filter(lambda x: path in x[1]["inputs"], leaderboard.items()))
    #         )
    #     print(_create_leaderboard(filtered_board, metric))
    # else:
    #     print(_create_leaderboard(leaderboard, metric))


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--format", default="ascii", help="Choose an output format.")
@click.option(
    "--diff", nargs=2, help="Print the difference between two model revisions"
)
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def params(revision, format, paths, diff):
    """List the parameters of astroquery requests"""

    def _param_value(rdf_iteral):
        if not type(rdf_iteral) != rdflib.term.Literal:
            return rdf_iteral
        if rdf_iteral.isnumeric():
            return rdf_iteral.__str__()
        else:
            return rdf_iteral.toPython()

    graph = _graph(revision, paths)
    # model_params = dict()
    # how to use ontology
    output = PrettyTable()
    output.field_names = ["Run ID", "AstroQuery Module", "Astro Object"]
    output.align["Run ID"] = "l"

    query_where = """WHERE {{
        ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object;
             <http://odahub.io/ontology#isUsing> ?aq_module;
             ^oa:hasBody/oa:hasTarget ?runId .
        ?a_object <http://purl.org/dc/terms/title> ?a_object_name .
        ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .
        ?run ?p ?o .
        }}"""

    for r in graph.query(f"""
        SELECT DISTINCT ?run ?runId ?a_object ?a_object_name ?aq_module ?aq_module_name 
        {query_where}
        """):
        output.add_row([
            _run_id(r.runId),
            r.aq_module_name,
            r.a_object_name
        ])

    print(output)

    r = graph.query(f"""
    CONSTRUCT {{
        ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object .
        ?run <http://odahub.io/ontology#isUsing> ?aq_module .
        ?run ?p ?o .
    }}
    {query_where}
    """)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#")  # the same
    G.bind("local-renku", "file:///home/savchenk/work/oda/renku/renku-aqs/renku-aqs-test-case/.renku/")  # ??

    serial = G.serialize(format="n3").decode()

    print(serial)

    with open("subgraph.ttl", "w") as f:
        f.write(serial)

    # TODO: do construct and ingest into ODA KG
    # TODO: plot construct

    #     output.field_names = ["Run ID", "Model", "Hyper-Parameters"]
    #     output.align["Run ID"] = "l"
    #     output.align["Model"] = "l"
    #     output.align["Hyper-Parameters"] = "l"
    #     for runid, v in model_params.items():
    #         output.add_row([runid, v["algorithm"], json.dumps(v["hp"])])
    #     print(output)

    # for r in graph.query(
    #     """SELECT ?runId ?algo ?hp ?value where {{
    #     ?run a aqs:Run ;
    #     aqs:hasInput ?in .
    #     ?in a aqs:HyperParameterSetting .
    #     ?in aqs:specifiedBy/rdfs:label ?hp .
    #     ?in aqs:hasValue ?value .
    #     ?run aqs:implements/rdfs:label ?algo ;
    #     ^oa:hasBody/oa:hasTarget ?runId
    #     }}"""
    # # ):
    #     run_id = _run_id(r.runId)
    #     if run_id in model_params:
    #         model_params[run_id]["hp"][str(r.hp)] = _param_value(r.value)
    #     else:
    #         model_params[run_id] = dict(
    #             {"algorithm": str(r.algo), "hp": {str(r.hp): _param_value(r.value)}}
    #         )

    # if len(diff) > 0:
    #     for r in diff:
    #         if r not in model_params:
    #             print("Unknown revision provided for diff parameter: {}".format(r))
    #             return
    #     if model_params[diff[0]]["algorithm"] != model_params[diff[1]]["algorithm"]:
    #         print("Model:")
    #         print("\t- {}".format(model_params[diff[0]]["algorithm"]))
    #         print("\t+ {}".format(model_params[diff[1]]["algorithm"]))
    #     else:
    #         params_diff = DeepDiff(
    #             model_params[diff[0]], model_params[diff[1]], ignore_order=True
    #         )
    #         output = PrettyTable()
    #         output.field_names = ["Hyper-Parameter", "Old", "New"]
    #         output.align["Hyper-Parameter"] = "l"
    #         if "values_changed" not in params_diff:
    #             print(output)
    #             return
    #         for k, v in params_diff["values_changed"].items():
    #             parameter_name = re.search(r"\['(\w+)'\]$", k).group(1)
    #             output.add_row(
    #                 [
    #                     parameter_name,
    #                     _param_value(v["new_value"]),
    #                     _param_value(v["old_value"]),
    #                 ]
    #             )
    #         print(output)
    # else:
    #     output = PrettyTable()
    #     output.field_names = ["Run ID", "Model", "Hyper-Parameters"]
    #     output.align["Run ID"] = "l"
    #     output.align["Model"] = "l"
    #     output.align["Hyper-Parameters"] = "l"
    #     for runid, v in model_params.items():
    #         output.add_row([runid, v["algorithm"], json.dumps(v["hp"])])
    #     print(output)


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--filename", default="graph.png", help="The filename of the output file image")
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def display(revision, paths, filename):
    """Simple graph visualization """
    import io
    from IPython.display import display
    import pydotplus

    graph = _graph(revision, paths)

    renku_path = renku_context().renku_path

    query_where = """WHERE {{
            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ; 
                <http://odahub.io/ontology#isUsing> ?aq_module ;
                <http://purl.org/dc/terms/title> ?run_name ;
                 ^oa:hasBody/oa:hasTarget ?runId ;
                 rdf:type ?run_rdf_type .
                 
                 
            ?a_object <http://purl.org/dc/terms/title> ?a_object_name ; 
                rdf:type ?a_obj_rdf_type .
                
            ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name ; 
                rdf:type ?aq_mod_rdf_type .
                
            FILTER (!CONTAINS(str(?a_object), " ")) .

            }}"""

    r = graph.query(f"""
        CONSTRUCT {{
            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                <http://odahub.io/ontology#isUsing> ?aq_module ;
                <http://purl.org/dc/terms/title> ?run_name ;
                rdf:type ?run_rdf_type .
                
            ?a_object <https://odahub.io/ontology#AstroObject> ?a_object_name ;
                rdf:type ?a_obj_rdf_type .
                
            ?aq_module <https://odahub.io/ontology#AQModule> ?aq_module_name ;
                rdf:type ?aq_mod_rdf_type .
            
        }}
        {query_where}
        """)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#") # the same
    G.bind("local-renku", f"file://{renku_path}/")

    serial = G.serialize(format="n3").decode()

    print(serial)

    with open("subgraph.ttl", "w") as f:
        f.write(serial)

    stream = io.StringIO()
    rdf2dot.rdf2dot(G, stream, opts={display})
    pydot_graph = pydotplus.graph_from_dot_data(stream.getvalue())
    pydot_graph.write_png(filename)
