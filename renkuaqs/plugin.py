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
import json

import click
import rdflib
import rdflib.tools.rdf2dot

from pathlib import Path

from rdflib.tools import rdf2dot
from renku.core.models.cwl.annotation import Annotation
from renku.core.incubation.command import Command
from renku.core.plugins import hookimpl
from renku.core.models.provenance.provenance_graph import ProvenanceGraph
from renku.core.errors import RenkuException
from renku.core.management import LocalClient

from prettytable import PrettyTable
from aqsconverters.io import AQS_DIR, COMMON_DIR

import time
import yaml

import renkuaqs.graph_utils as graph_utils

graph_configuration = yaml.load(open("../graph_config.yaml"), Loader=yaml.SafeLoader)


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
    # One detail I forgot to mention,
    # `renku log` is now more like `git log` in that is shows a history of past commands/executions.
    # To get the JSON-LD, we have a new command `renku graph export`.
    # That command can export the whole metadata of the repository with `renku graph export --full`
    # or for a single commit using `renku graph export --revision <commit>`
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

    renku_path = renku_context().renku_path

    # model_params = dict()
    # how to use ontology
    output = PrettyTable()
    output.field_names = ["Run ID", "AstroQuery Module", "Astro Object"]
    output.align["Run ID"] = "l"

    # for the query_object
    query_where = """WHERE {{
        ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
             <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
             ^oa:hasBody/oa:hasTarget ?runId .
        
        OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

        ?a_object <http://purl.org/dc/terms/title> ?a_object_name .
        
        ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .

        ?run ?p ?o .

        }}"""

    invalid_entries = 0

    for r in graph.query(f"""
        SELECT DISTINCT ?run ?runId ?a_object ?a_object_name ?aq_module ?aq_module_name 
        {query_where}
        """):
        if " " in r.a_object:
            invalid_entries += 1
        else:
            output.add_row([
                _run_id(r.runId),
                r.aq_module_name,
                r.a_object_name
            ])
    print(output, "\n")

    # for the query_region
    query_where = """WHERE {{
        ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
             <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region ;
             ^oa:hasBody/oa:hasTarget ?runId .
        
        OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

        ?a_region <http://purl.org/dc/terms/title> ?a_region_name .
        
        ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .

        ?run ?p ?o .
    }}"""

    output = PrettyTable()
    output.field_names = ["Run ID", "AstroQuery Module", "Astro Region"]
    output.align["Run ID"] = "l"
    for r in graph.query(f"""
        SELECT DISTINCT ?run ?runId ?a_region ?a_region_name ?aq_module ?aq_module_name 
        {query_where}
        """):
        if " " in r.a_region:
            invalid_entries += 1
        else:
            output.add_row([
                _run_id(r.runId),
                r.aq_module_name,
                r.a_region_name
            ])
    print(output, "\n")

    # for the get_images
    query_where = """WHERE {{
        ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
             <http://odahub.io/ontology#isRequestingAstroImage> ?a_image ;
             ^oa:hasBody/oa:hasTarget ?runId .

        OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

        ?a_image <http://purl.org/dc/terms/title> ?a_image_name .

        ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .

        ?run ?p ?o .
    }}"""

    output = PrettyTable()
    output.field_names = ["Run ID", "AstroQuery Module", "Astro Image"]
    output.align["Run ID"] = "l"
    for r in graph.query(f"""
        SELECT DISTINCT ?run ?runId ?a_image ?a_image_name ?aq_module ?aq_module_name 
        {query_where}
        """):
        if " " in r.a_image:
            invalid_entries += 1
        else:
            output.add_row([
                _run_id(r.runId),
                r.aq_module_name,
                r.a_image_name
            ])

    print(output, "\n")
    if invalid_entries > 0:
        print("Some entries within the graph are not valid and therefore the store should be recreated", "\n")

    query_where = """WHERE {{
            {
                ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                     <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                     ^oa:hasBody/oa:hasTarget ?runId .
                 
                ?a_object <http://purl.org/dc/terms/title> ?a_object_name .
                
                ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .
                
                OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}
                
                ?run ?p ?o .

                FILTER (!CONTAINS(str(?a_object), " ")) .
            
            }
            UNION
            {
                ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                     <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region ;
                     ^oa:hasBody/oa:hasTarget ?runId .
                
                ?a_region a ?a_region_type ; 
                    <http://purl.org/dc/terms/title> ?a_region_name ;
                    <http://odahub.io/ontology#isUsingSkyCoordinates> ?a_sky_coordinates ;
                    <http://odahub.io/ontology#isUsingRadius> ?a_radius .
                
                ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .

                OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}
                
                ?run ?p ?o .
            }
            UNION
            {
                ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                     <http://odahub.io/ontology#isRequestingAstroImage> ?a_image ;
                     ^oa:hasBody/oa:hasTarget ?runId .
                
                ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .
                
                ?a_image a ?a_image_type ;
                        <http://purl.org/dc/terms/title> ?a_image_name .
                        
                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingSkyCoordinates> ?a_sky_coordinates . }}
                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingRadius> ?a_radius . }}
                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingPixels> ?a_pixels . }}
                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingImageBand> ?a_image_band . }}

                OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}
                
                ?run ?p ?o .
            }
            }}"""

    r = graph.query(f"""
        CONSTRUCT {{
            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object .
            ?run <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region .
            ?run <http://odahub.io/ontology#isRequestingAstroImage> ?a_image .
            ?run <http://purl.org/dc/terms/title> ?run_title .
            ?run <http://odahub.io/ontology#isUsing> ?aq_module .
            ?run ?p ?o .
            
            ?a_region a ?a_region_type ; 
                <http://purl.org/dc/terms/title> ?a_region_name ;
                <http://odahub.io/ontology#isUsingSkyCoordinates> ?a_sky_coordinates ;
                <http://odahub.io/ontology#isUsingRadius> ?a_radius .
                
            ?a_image a ?a_image_type ;
                <http://purl.org/dc/terms/title> ?a_image_name ;
                <http://odahub.io/ontology#isUsingSkyCoordinates> ?a_sky_coordinates ;
                <http://odahub.io/ontology#isUsingRadius> ?a_radius ;
                <http://odahub.io/ontology#isUsingPixels> ?a_pixels ;
                <http://odahub.io/ontology#isUsingImageBand> ?a_image_band .
        }}
        {query_where}
        """)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#")   # the same
    G.bind("local-renku", f"file://{renku_path}/") #??

    serial = G.serialize(format="n3").decode()

    with open("subgraph.ttl", "w") as f:
        f.write(serial)


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--filename", default="graph.png", help="The filename of the output file image")
@click.option("--input-notebook", default=None, help="Input notebook to process")
@click.option("--no-oda-info", is_flag=True, help="Exclude oda related information in the output graph")
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def display(revision, paths, filename, no_oda_info, input_notebook):
    """Simple graph visualization """
    import io
    from IPython.display import display
    import pydotplus

    graph = _graph(revision, paths)

    renku_path = renku_context().renku_path

    query_where = graph_utils.build_query_where(input_notebook=input_notebook)
    query_construct = graph_utils.build_query_construct(input_notebook=input_notebook, no_oda_info=no_oda_info)

    query = f"""{query_construct}
        {query_where}
        """

    print("Before starting the query")
    t1 = time.perf_counter()
    r = graph.query(query)
    t2 = time.perf_counter()
    print("Query completed in %d !" % (t2 - t1))

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#") # the same
    G.bind("local-renku", f"file://{renku_path}/")

    graph_utils.extract_activity_start_time(G)

    if not no_oda_info:
        # process oda-related information (eg do the inferring)
        graph_utils.process_oda_info(G)

    action_node_dict = {}
    type_label_values_dict = {}
    args_default_value_dict = {}
    in_default_value_dict = {}
    out_default_value_dict = {}

    graph_utils.analyze_inputs(G, in_default_value_dict)
    graph_utils.analyze_arguments(G, action_node_dict, args_default_value_dict)
    graph_utils.analyze_outputs(G, out_default_value_dict)
    graph_utils.analyze_types(G, type_label_values_dict)

    graph_utils.clean_graph(G)

    stream = io.StringIO()
    rdf2dot.rdf2dot(G, stream, opts={display})
    pydot_graph = pydotplus.graph_from_dot_data(stream.getvalue())

    # list of edges and simple color change
    for edge in pydot_graph.get_edge_list():
        graph_utils.customize_edge(edge)

    for node in pydot_graph.get_nodes():
        node_type = graph_utils.get_node_type(node, type_label_values_dict=type_label_values_dict)
        # get configuration
        print("node_type: ", node_type)

        print("node_configuration: ", graph_configuration.get(node_type, None))
        graph_utils.customize_node(node,
                                   graph_configuration,
                                   node_type,
                                   node_configuration=graph_configuration.get(node_type, graph_configuration['Default']),
                                   type_label_values_dict=type_label_values_dict
                                   )

    # final output write over the png image
    pydot_graph.write_png(filename)
