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
import webbrowser
import click
import rdflib
import rdflib.tools.rdf2dot
import time
import yaml

from pathlib import Path
from pyvis.network import Network
from rdflib.tools import rdf2dot
from renku.core.models.provenance.annotation import Annotation
from renku.core.management.command_builder import Command, inject
from renku.core.management.interface.client_dispatcher import IClientDispatcher
from renku.core.plugins import hookimpl
from renku.core.commands.format.graph import _conjunctive_graph
from renku.core.errors import RenkuException
from renku.core.management.client import LocalClient

from renku.core.commands.graph import _get_graph_for_all_objects

from prettytable import PrettyTable
from aqsconverters.io import AQS_DIR, COMMON_DIR

import renkuaqs.graph_utils as graph_utils

# TODO improve this
__this_dir__ = os.path.join(os.path.abspath(os.path.dirname(__file__)))
graph_configuration = yaml.load(open(os.path.join(__this_dir__, "graph_config.yaml")), Loader=yaml.SafeLoader)


class AQS(object):
    def __init__(self, run):
        self.run = run

    @property
    @inject.autoparams("client_dispatcher")
    def renku_aqs_path(self, client_dispatcher: IClientDispatcher):
        """Return a ``Path`` instance of Renku AQS metadata folder."""
        return Path(client_dispatcher.current_client.renku_home).joinpath(AQS_DIR).joinpath(COMMON_DIR)

    def load_model(self, path):
        """Load AQS reference file."""
        if path and path.exists():
            return json.load(path.open())
        return {}


@hookimpl
def activity_annotations(activity):
    """``process_run_annotations`` hook implementation."""
    aqs = AQS(activity)

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
                    activity=activity.id, id=model_id
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


def _export_graph():
    graph = _get_graph_for_all_objects()

    return graph


def _graph(revision, paths):
    # FIXME: use (revision, paths) filter

    cmd = Command().command(_export_graph).with_database(write=False).require_migration()
    cmd_result = cmd.build().execute()

    if cmd_result.status == cmd_result.FAILURE:
        raise RenkuException("fail to export the renku graph")
    graph = _conjunctive_graph(cmd_result.output)

    graph.bind("aqs", "http://www.w3.org/ns/aqs#")
    graph.bind("oa", "http://www.w3.org/ns/oa#")
    graph.bind("xsd", "http://www.w3.org/2001/XAQSchema#")

    return graph


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

                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingCoordinates> ?a_coordinates . }}
                OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingPosition> ?a_position . }}
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
                <http://odahub.io/ontology#isUsingCoordinates> ?a_coordinates ;
                <http://odahub.io/ontology#isUsingPosition> ?a_position ;
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

    html_fn = 'graph.html'
    renku_path = renku_context().renku_path

    query_where = graph_utils.build_query_where(input_notebook=input_notebook)
    # query_construct = graph_utils.build_query_construct(input_notebook=input_notebook, no_oda_info=no_oda_info)
    query_construct = graph_utils.build_query_construct_base_graph()

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

    with open('type_label_values_dict.yaml', 'w+') as ft:
        yaml.dump(type_label_values_dict, ft, allow_unicode=True)

    graph_utils.clean_graph(G)

    stream = io.StringIO()
    rdf2dot.rdf2dot(G, stream, opts={display})
    with open('graph.dot', 'w+') as fd:
        rdf2dot.rdf2dot(G, fd)
    pydot_graph = pydotplus.graph_from_dot_data(stream.getvalue())

    # pyvis graph
    net = Network(
        height='750px', width='100%',
    )
    # TODO not fully working yet, needs to investigate
    # netx = nx.drawing.nx_pydot.read_dot('graph.dot')
    # net.from_nx(netx)

    graph_utils.set_graph_options(net)

    hidden_nodes_dic = {}
    hidden_edges = []

    for node in pydot_graph.get_nodes():
        id_node = graph_utils.get_id_node(node)
        print("id_node: ", id_node)
        if id_node is not None and id_node in type_label_values_dict:
            type_node = type_label_values_dict[id_node]
            node_label, node_title = graph_utils.get_node_graphical_info(node, type_node)
            print("node_label: ", node_label)
            print("node_title: ", node_title)
            node_configuration = graph_configuration.get(type_node,
                                                         graph_configuration['Default'])
            node_value = node_configuration.get('value', graph_configuration['Default']['value'])
            node_level = node_configuration.get('level', graph_configuration['Default']['level'])
            hidden = False
            if type_node.startswith('CommandOutput') or type_node.startswith('CommandInput') \
                    or type_node.startswith('Angle') or type_node.startswith('Pixels') \
                    or type_node.startswith('Coordinates') or type_node.startswith('Position') \
                    or type_node.startswith('SkyCoordinates'):
                hidden = True
            if not hidden:
                net.add_node(node.get_name(),
                             label=node_label,
                             title=node_title,
                             type=type_node,
                             color=node_configuration['color'],
                             level=node_level,
                             shape=node_configuration['shape'],
                             font={
                                 'multi': "html",
                                 'face': "courier"
                             })
            else:
                node_info = dict(
                    id=node.get_name(),
                    label=node_label,
                    title=node_title,
                    type=type_node,
                    color=node_configuration['color'],
                    shape=node_configuration['shape'],
                    level=node_level,
                    font={
                        'multi': "html",
                        'face': "courier"
                    }
                )
                hidden_nodes_dic[node.get_name()] = node_info
        # for the png output
        graph_utils.customize_node(node,
                                   graph_configuration,
                                   type_label_values_dict=type_label_values_dict
                                   )

    # list of edges and simple color change
    for edge in pydot_graph.get_edge_list():
        edge_label = graph_utils.get_edge_label(edge)
        source_node = edge.get_source()
        dest_node = edge.get_destination()
        hidden = False
        edge_id = (source_node + '_' + dest_node)
        if edge_label.startswith('isInputOf') or edge_label.startswith('hasOutputs') \
                or edge_label.startswith('isUsing'):
            hidden = True
        if source_node is not None and dest_node is not None:
            if not hidden:
                net.add_edge(source_node, dest_node,
                             id=edge_id,
                             title=edge_label)
            else:
                edge_info = dict(
                    source_node=source_node,
                    dest_node=dest_node,
                    id=edge_id,
                    title=edge_label
                )
                hidden_edges.append(edge_info)
        # for the png putput
        graph_utils.customize_edge(edge)

    # to tweak physics related options
    net.write_html(html_fn)

    graph_utils.add_js_click_functionality(net, html_fn, hidden_nodes_dic, hidden_edges)

    graph_utils.update_vis_library_version(html_fn)

    webbrowser.open(html_fn)
    # final output write over the png image
    pydot_graph.write_png(filename)
