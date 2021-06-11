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
import re
import sys
import json
import click
import rdflib
from copy import deepcopy
from pathlib import Path

from renku.core.models.cwl.annotation import Annotation
from renku.core.incubation.command import Command
from renku.core.plugins import hookimpl
from renku.core.models.provenance.provenance_graph import ProvenanceGraph
from renku.core.errors import RenkuException

from prettytable import PrettyTable
from deepdiff import DeepDiff

from aqsconverters.models import Run
from aqsconverters.io import AQS_DIR, COMMON_DIR


class AQS(object):
    def __init__(self, run):
        self.run = run
        self.use_fake_models = True

    @property
    def renku_aqs_path(self):
        """Return a ``Path`` instance of Renku AQS metadata folder."""
        return Path(".renku/aq")
        #return Path(self.run.client.renku_home).joinpath(AQS_DIR).joinpath(COMMON_DIR)

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
    os.remove("../sitecustomize.py")
    
    annotations = []

    if os.path.exists(aqs.renku_aqs_path):
        for p in aqs.renku_aqs_path.iterdir():
            if aqs.use_fake_models:
                print(f"found annotation: {p}")
                print(open(p).read())
            else:
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

    # where to get renku.client and dir?

    annotations_dir = os.path.abspath(".renku/aq")
    os.makedirs(annotations_dir, exist_ok=True)

    #fn = os.path.join(sys.path[0], "sitecustomize.py")
    fn = "../sitecustomize.py"

    print(f"\033[34msitecustomize.py as {fn}\033[0m")    

    open(fn, "w").write("""
print(f"\033[31mHERE enable hooks for astroquery\033[0m")  

import os
import json
import random

import astroquery
astroquery.hooked = True

import astroquery.query

def produce_annotation(self, *args, **kwargs):
    aq_module_name = self.__class__.__name__    

    print("\033[33mpatched query_object with:\033[0m", args, kwargs)    
    print("\033[33mwriting annotation here:\033[0m", aq_module_name, args, kwargs)    

    json.dump(
        {
            "aq_module": aq_module_name,
            "args": [str(a) for a in args],
            "kwargs": {k:str(v) for k,v in kwargs.items()}
        },
        open(os.path.join("%s", f"run-{random.randint(0, 100000)}.json"), "w"),
        sort_keys=True,
        indent=4,
    )


def aqs_query_object(self, *args, **kwargs):
    produce_annotation(self, *args, **kwargs)

    return object.__getattribute__(self, 'query_object')(*args, **kwargs)

def aqs_query_region(self, *args, **kwargs):
    produce_annotation(self, *args, **kwargs)

    return object.__getattribute__(self, 'query_region')(*args, **kwargs)
    
    
def asq_BaseQuery_getattribute(self, name):
    if name == "query_object":
        return lambda *a, **aa: aqs_query_object(self, *a, **aa)

    if name == "query_region":
        return lambda *a, **aa: aqs_query_region(self, *a, **aa)

    #print("\033[33mpatching BaseQuery_getattr!\033[0m", name)
    return object.__getattribute__(self, name)

astroquery.query.BaseQuery.__getattribute__ = asq_BaseQuery_getattribute

"""%annotations_dir)

    from astroquery.query import BaseQuery

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
    for r in graph.query(
        """SELECT DISTINCT ?type ?value ?run ?runId ?dsPath where {{
        ?em a aqs:ModelEvaluation ;
        aqs:hasValue ?value ;
        aqs:specifiedBy ?type ;
        ^aqs:hasOutput/aqs:implements/rdfs:label ?run ;
        ^aqs:hasOutput/^oa:hasBody/oa:hasTarget ?runId ;
        ^aqs:hasOutput/^oa:hasBody/oa:hasTarget/prov:qualifiedUsage/prov:entity/prov:atLocation ?dsPath
        }}"""
    ):
        run_id = _run_id(r.runId)
        metric_type = r.type.split("#")[1]
        if run_id in leaderboard:
            leaderboard[run_id]["inputs"].append(r.dsPath.__str__())
            continue
        leaderboard[run_id] = {
            metric_type: r.value.value,
            "model": r.run,
            "inputs": [r.dsPath.__str__()],
        }
    if len(paths):
        filtered_board = dict()
        for path in paths:
            filtered_board.update(
                dict(filter(lambda x: path in x[1]["inputs"], leaderboard.items()))
            )
        print(_create_leaderboard(filtered_board, metric))
    else:
        print(_create_leaderboard(leaderboard, metric))


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
    model_params = dict()
    for r in graph.query(
        """SELECT ?runId ?algo ?hp ?value where {{
        ?run a aqs:Run ;
        aqs:hasInput ?in .
        ?in a aqs:HyperParameterSetting .
        ?in aqs:specifiedBy/rdfs:label ?hp .
        ?in aqs:hasValue ?value .
        ?run aqs:implements/rdfs:label ?algo ;
        ^oa:hasBody/oa:hasTarget ?runId
        }}"""
    ):
        run_id = _run_id(r.runId)
        if run_id in model_params:
            model_params[run_id]["hp"][str(r.hp)] = _param_value(r.value)
        else:
            model_params[run_id] = dict(
                {"algorithm": str(r.algo), "hp": {str(r.hp): _param_value(r.value)}}
            )

    if len(diff) > 0:
        for r in diff:
            if r not in model_params:
                print("Unknown revision provided for diff parameter: {}".format(r))
                return
        if model_params[diff[0]]["algorithm"] != model_params[diff[1]]["algorithm"]:
            print("Model:")
            print("\t- {}".format(model_params[diff[0]]["algorithm"]))
            print("\t+ {}".format(model_params[diff[1]]["algorithm"]))
        else:
            params_diff = DeepDiff(
                model_params[diff[0]], model_params[diff[1]], ignore_order=True
            )
            output = PrettyTable()
            output.field_names = ["Hyper-Parameter", "Old", "New"]
            output.align["Hyper-Parameter"] = "l"
            if "values_changed" not in params_diff:
                print(output)
                return
            for k, v in params_diff["values_changed"].items():
                parameter_name = re.search(r"\['(\w+)'\]$", k).group(1)
                output.add_row(
                    [
                        parameter_name,
                        _param_value(v["new_value"]),
                        _param_value(v["old_value"]),
                    ]
                )
            print(output)
    else:
        output = PrettyTable()
        output.field_names = ["Run ID", "Model", "Hyper-Parameters"]
        output.align["Run ID"] = "l"
        output.align["Model"] = "l"
        output.align["Hyper-Parameters"] = "l"
        for runid, v in model_params.items():
            output.add_row([runid, v["algorithm"], json.dumps(v["hp"])])
        print(output)