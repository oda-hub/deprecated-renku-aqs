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
import pathlib
import json
import click
import rdflib
import rdflib.tools.rdf2dot

from pathlib import Path

from matplotlib.table import table
from rdflib.tools import rdf2dot
from renku.core.models.cwl.annotation import Annotation
from renku.core.incubation.command import Command
from renku.core.plugins import hookimpl
from renku.core.models.provenance.provenance_graph import ProvenanceGraph
from renku.core.errors import RenkuException
from renku.core.management import LocalClient

from prettytable import PrettyTable

from aqsconverters.io import AQS_DIR, COMMON_DIR
from six import b


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

    query_where = """WHERE {{
        ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object;
             <http://odahub.io/ontology#isUsing> ?aq_module;
             ^oa:hasBody/oa:hasTarget ?runId .

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
                r.a_object_name,
            ])

    print(output, "\n")
    if invalid_entries > 0:
        print("Some entries within the graph are not valid and therefore the store should be recreated", "\n")

    query_where = """WHERE {{
            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object;
                 <http://odahub.io/ontology#isUsing> ?aq_module;
                 ^oa:hasBody/oa:hasTarget ?runId .

            ?a_object <http://purl.org/dc/terms/title> ?a_object_name .

            ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .
    
            ?run ?p ?o .

            FILTER (!CONTAINS(str(?a_object), " ")) .

            }}"""

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
    G.bind("odas", "https://odahub.io/ontology#")   # the same
    G.bind("local-renku", f"file://{renku_path}/") #??

    serial = G.serialize(format="n3").decode()

    print(serial)

    with open("subgraph.ttl", "w") as f:
        f.write(serial)


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--filename", default="graph.png", help="The filename of the output file image")
@click.option("--no-oda-info", is_flag=True, help="Exclude oda related out in the output graph")
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def display(revision, paths, filename, no_oda_info):
    """Simple graph visualization """
    import io
    from IPython.display import display
    from rdflib.tools.rdf2dot import LABEL_PROPERTIES
    import pydotplus
    from lxml import etree

    def label(x, g):

        for labelProp in LABEL_PROPERTIES:
            l = g.value(x, labelProp)
            if l:
                return l

        try:
            return g.namespace_manager.compute_qname(x)[2]
        except:
            return x

    graph = _graph(revision, paths)

    renku_path = renku_context().renku_path

    query_where = """WHERE {{
            ?action a <http://schema.org/Action> ; 
                <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                ?has ?actionParam .
                
            FILTER (?has IN (<https://swissdatasciencecenter.github.io/renku-ontology#hasArguments>, 
                <https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs>, 
                <https://swissdatasciencecenter.github.io/renku-ontology#hasInputs>))
            
            ?actionParam a ?actionParamType ;
                <http://schema.org/valueReference> ?parameter_value ;
                <http://schema.org/defaultValue> ?actionParamValue .
                
            OPTIONAL { ?actionParam <https://swissdatasciencecenter.github.io/renku-ontology#prefix> ?actionPrefix }
            OPTIONAL { ?actionParam <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition }
                 
             FILTER (?actionParamType IN (<https://swissdatasciencecenter.github.io/renku-ontology#CommandOutput>, 
                <https://swissdatasciencecenter.github.io/renku-ontology#CommandInput>, 
                <https://swissdatasciencecenter.github.io/renku-ontology#CommandParameter>))
            
            ?parameter_value a ?parameter_valueType .
            
            ?activity a ?activityType ;
                <https://swissdatasciencecenter.github.io/renku-ontology#parameter> ?parameter_value .
            
            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                <http://odahub.io/ontology#isUsing> ?aq_module ;
                <http://purl.org/dc/terms/title> ?run_name ;
                a ?run_rdf_type ;
                ^oa:hasBody/oa:hasTarget ?runId ;
                ^oa:hasBody/oa:hasTarget ?activity .

            ?a_object <http://purl.org/dc/terms/title> ?a_object_name ;
                a ?a_obj_rdf_type .

            ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name ;
                a ?aq_mod_rdf_type .
                
            FILTER (!CONTAINS(str(?a_object), " ")) .
            }}"""

    query_construct_action = """
            ?action a <http://schema.org/Action> ;
                <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                ?has ?actionParam .
        
            ?actionParam a ?actionParamType ;
                <https://swissdatasciencecenter.github.io/renku-ontology#prefix> ?actionPrefix ;
                <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition ;
                <http://schema.org/valueReference> ?parameter_value ;
                <http://schema.org/defaultValue> ?actionParamValue .
    """

    query_construct_oda_info = ""
    if not no_oda_info:
        query_construct_oda_info += """
            ?parameter_value a ?parameter_valueType .

            ?activity a ?activityType ;
                <https://swissdatasciencecenter.github.io/renku-ontology#parameter> ?parameter_value .

            ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                <http://odahub.io/ontology#isUsing> ?aq_module ;
                <http://purl.org/dc/terms/title> ?run_name ;
                oa:hasTarget ?activity ;
                a ?run_rdf_type .

            ?a_object <https://odahub.io/ontology#AstroObject> ?a_object_name ;
                a ?a_obj_rdf_type .

            ?aq_module <https://odahub.io/ontology#AQModule> ?aq_module_name ;
                a ?aq_mod_rdf_type .
        """

    query_construct = f"""CONSTRUCT {{
            {query_construct_action}
                
            {query_construct_oda_info}
                
        }}"""

    query = f"""{query_construct}
        {query_where}
        """
    r = graph.query(query)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#") # the same
    G.bind("local-renku", f"file://{renku_path}/")

    # write over a ttl file
    serial = G.serialize(format="n3").decode()

    with open("subgraph.ttl", "w") as f:
        f.write(serial)

    stream = io.StringIO()

    action_node_dict = {}

    type_label_values_dict = {}

    args_default_value_dict = {}

    in_default_value_dict = {}

    out_default_value_dict = {}

    # analyze inputs
    inputs_list = G[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasInputs')]
    for s, o in inputs_list:
        s_label = label(s, G)
        if s_label not in in_default_value_dict:
            in_default_value_dict[s_label] = []
        input_obj_list = list(G[o])
        for input_p, input_o in input_obj_list:
            if input_p.n3() == "<http://schema.org/defaultValue>":
                in_default_value_dict[s_label].append(input_o.n3().strip('\"'))
        # infer isInputOf property
        G.add((o, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#isInputOf'), s))
        G.remove((s, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasInputs'), o))

    # analyze arguments
    args_list = G[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasArguments')]
    for s, o in args_list:
        print("s: ", s)
        print("o: ", o)
        s_label = label(s, G)
        if s_label not in action_node_dict:
            action_node_dict[s_label] = s
        if s_label not in args_default_value_dict:
            args_default_value_dict[s_label] = []
        arg_obj_list = list(G[o])
        for arg_p, arg_o in arg_obj_list:
            if arg_p.n3() == "<http://schema.org/defaultValue>":
                prefix_value = ""
                # get, if there, the prefix
                prefix_o = list(G.objects(
                    subject=o,
                    predicate=rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#prefix')))
                if prefix_o is not None and len(prefix_o) > 0:
                    prefix_value = prefix_o[0].value
                    G.remove((o, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#prefix'), prefix_o[0]))
                # get the position
                position_o = list(G.objects(
                    subject=o,
                    predicate=rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#position')))
                if position_o is not None and len(position_o) > 0:
                    args_default_value_dict[s_label].append((prefix_value + arg_o.n3().strip('\"'), position_o[0].value))
                    G.remove((o, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#position'), position_o[0]))
                G.remove((o, arg_p, arg_o))
        # print("args_default_value_dict: ", args_default_value_dict)
        G.remove((s, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasArguments'), o))

    # # infer isArgumentOf property for each action
    for action in args_default_value_dict.keys():
        args_pos_list = args_default_value_dict[action].copy()
        args_pos_list.sort(key=lambda y: y[1])
        sorted_args = ' '.join(t[0] for t in args_pos_list)
        node_args = rdflib.URIRef("https://swissdatasciencecenter.github.io/renku-ontology#CommandParameter")
        G.add((node_args,
               rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#isArgumentOf'),
               action_node_dict[action]))
        # value for the node args
        G.add((node_args,
               rdflib.URIRef('http://schema.org/defaultValue'),
               rdflib.Literal(sorted_args.strip())))

    # analyze outputs
    outputs_list = G[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs')]
    for s, o in outputs_list:
        s_label = label(s, G)
        if s_label not in out_default_value_dict:
            out_default_value_dict[s_label] = []
        output_obj_list = list(G[o])
        for output_s, output_o in output_obj_list:
            if output_s.n3() == "<http://schema.org/defaultValue>":
                out_default_value_dict[s_label].append(output_o.n3().strip('\"'))

    # remove value reference in case we plot no_oda_info
    if no_oda_info:
        outputs_list = G[:rdflib.URIRef('http://schema.org/valueReference')]
        for s, o in outputs_list:
            G.remove((s, rdflib.URIRef('http://schema.org/valueReference'), o))

    # analyze types
    types_list = G[:rdflib.RDF.type]
    for s, o in types_list:
        s_qname = G.compute_qname(o)
        s_label = label(s, G)
        type_label_values_dict[s_label] = s_qname[2]
        G.remove((s, rdflib.RDF.type, o))

    rdf2dot.rdf2dot(G, stream, opts={display})
    pydot_graph = pydotplus.graph_from_dot_data(stream.getvalue())

    # list of edges and simple color change
    for edge in pydot_graph.get_edge_list():
        # simple color code
        if 'rdf:type' in edge.obj_dict['attributes']['label']:
            edge.obj_dict['attributes']['color'] = 'RED'
        if 'oda:isRequestingAstroObject' in edge.obj_dict['attributes']['label']:
            edge.obj_dict['attributes']['color'] = 'BLUE'
        if 'oda:isUsing' in edge.obj_dict['attributes']['label']:
            edge.obj_dict['attributes']['color'] = 'GREEN'

    default_value_table_row = "<tr>" \
                              "<td align='left'>{attribute_id}</td>" \
                              "<td align='left'>&quot;{attribute_default_value}&quot;</td>" \
                              "</tr>"
    for node in pydot_graph.get_nodes():
        if 'label' in node.obj_dict['attributes']:
            # parse the whole node table into a lxml object
            table_html = etree.fromstring(node.obj_dict['attributes']['label'][1:-1])
            tr_list = table_html.findall('tr')

            # modify the first row, hence the title of the node, and then all the rest
            id_node = None
            td_list_first_row = tr_list[0].findall('td')
            if td_list_first_row is not None:
                b_element_title = td_list_first_row[0].findall('B')
                if b_element_title is not None and b_element_title[0].text in type_label_values_dict:
                    id_node = b_element_title[0].text
                    b_element_title[0].text = type_label_values_dict[b_element_title[0].text]
                if id_node is not None:
                    # # put the arguments in the action tree node
                    # if id_node in args_default_value_dict.keys():
                    #     print("id_node: ", id_node)
                    #     print("args_default_value_dict[id_node]: ", args_default_value_dict[id_node])
                    #     # order the arguments according to their position
                    #     args_pos_list = args_default_value_dict[id_node].copy()
                    #     args_pos_list.sort(key=lambda y: y[1])
                    #     sorted_args = ' '.join(t[0] for t in args_pos_list)
                    #     # format the arguments table row
                    #     table_args_row_str = default_value_table_row.format(
                    #         attribute_id="arguments",
                    #         attribute_default_value=sorted_args
                    #     )
                    #     # parse the arguments and inputs table rows into a lxml object
                    #     table_args_row_element = etree.fromstring(table_args_row_str)
                    #     # add the row to the table
                    #     table_html.append(table_args_row_element)
                    if type_label_values_dict[id_node] == 'Action':
                        # color change
                        table_html.attrib['border'] = '2'
                        table_html.attrib['cellborder'] = '1'
                        table_html.attrib['color'] = '#dc143c'
                    # remove not-needed information in the output tree nodes (eg defaultValue text, position value)
                    if type_label_values_dict[id_node] == 'CommandOutput' or \
                            type_label_values_dict[id_node] == 'CommandInput':
                        # color change
                        table_html.attrib['border'] = '2'
                        table_html.attrib['cellborder'] = '1'
                        if type_label_values_dict[id_node] == 'CommandOutput':
                            table_html.attrib['color'] = '#FFFF00'
                        else:
                            table_html.attrib['color'] = '#00CC00'
                        for tr in tr_list:
                            list_td = tr.findall('td')
                            if len(list_td) == 2:
                                left_row_element_str = etree.tostring(list_td[0], encoding='unicode')
                                if 'defaultValue' in left_row_element_str:
                                    tr.remove(list_td[0])
                                    if 'align' in list_td[1].keys():
                                        list_td[1].attrib['align'] = 'center'
                                        list_td[1].attrib['colspan'] = '2'
                                if 'position' in left_row_element_str:
                                    table_html.remove(tr)
                # removal of the not-needed id table row
                table_html.remove(tr_list[1])
                # serialize back the table html
                node.obj_dict['attributes']['label'] = '< ' + etree.tostring(table_html, encoding='unicode') + ' >'
    pydot_graph.write_png(filename)
