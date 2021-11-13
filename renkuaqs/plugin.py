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

import glob
import itertools
import os
import pathlib
import re
import sys
import time
import json
from typing import DefaultDict, Optional, Tuple
import click
import rdflib
from nb2workflow.nbadapter import NotebookAdapter
import subprocess
from collections import defaultdict

import odakb.sparql

from copy import deepcopy
from pathlib import Path
from rdflib.graph import Graph

from renku.core.models.cwl.annotation import Annotation
from renku.core.incubation.command import Command
from renku.core.plugins import hookimpl
from renku.core.models.provenance.provenance_graph import ProvenanceGraph
from renku.core.errors import RenkuException

from prettytable import PrettyTable
from deepdiff import DeepDiff

#from aqsconverters.models import Run
from aqsconverters.io import AQS_DIR, COMMON_DIR

import io
from rdflib.tools import rdf2dot
import pydotplus
import requests
import yaml



def plot_graph(G, filename="graph.svg"):
    stream = io.StringIO()       

    rdf2dot.rdf2dot(G, stream, opts={})    

    dot_data = stream.getvalue()

    with open(filename.replace('.svg', '.dot'), "w") as f:
        f.write(dot_data)

    g = pydotplus.graph_from_dot_data(dot_data)
    g.prog = 'fdp' # or dot
    g.write_svg(filename)

    with open(filename.replace(".svg", ".ttl"), "w") as f:
        f.write(G.serialize(format='turtle'))

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

custom_bindings = {
        "aqs": "http://www.w3.org/ns/aqs#",
        "oa": "http://www.w3.org/ns/oa#",
        "xsd": "http://www.w3.org/2001/XAQSchema#",
        "oda": "http://odahub.io/ontology#",
        "dct": "http://purl.org/dc/terms/",
    }


def assign_default_bindings(G: rdflib.Graph) -> None:
    for k, v in custom_bindings.items():
        G.bind(k, v)


def _graph(revision, paths):
    # FIXME: use (revision, paths) filter
    cmd_result = Command().command(_load_provenance_graph).build().execute()

    provenance_graph = cmd_result.output
    provenance_graph.custom_bindings = custom_bindings

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


default_query_where = """
WHERE {
    ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object;
        <http://odahub.io/ontology#isUsing> ?aq_module;
        ^oa:hasBody/oa:hasTarget ?runId .
    ?a_object <http://purl.org/dc/terms/title> ?a_object_name .
    ?a_object ?o_p ?o_o .
    ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name .
    ?run ?p ?o .
    ?a_object ?obj_p ?obj_o .
}
"""

def extract_aq_subgraph(graph, query_where=None, to_file="subgraph.ttl"):
    if query_where is None:
        query_where = default_query_where

    query = f"""
    CONSTRUCT {{
        ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object .
        ?run <http://odahub.io/ontology#isUsing> ?aq_module .
        ?run ?p ?o .
        ?a_object ?obj_p ?obj_o .
    }}

    {query_where}
    """
    
    r = graph.query(query)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")

    assign_default_bindings(G)
    #G.bind("local-renku", "file:///home/savchenk/work/oda/renku/renku-aqs/renku-aqs-test-case/.renku/") #??

    serial = G.serialize(format="n3")

    if isinstance(serial, bytes):
        serial = serial.decode()
    
    #print(serial)

    if to_file is not None:
        with open(to_file, "w") as f:
            f.write(serial)

    return G


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
@click.option("-f", "--full", is_flag=True)
def params(revision, format, paths, diff, full):
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

    if full:
        query_where = """WHERE {{ ?run ?p ?o . }}""" # some loose selection here
    else:
        query_where = default_query_where

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

    extract_aq_subgraph(graph, query_where)

    #TODO: do construct and ingest into ODA KG
    #TODO: plot construct

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

def push_upstream():
    pass

@aqs.group()
@click.option("-u", "--upstream", default=None)
@click.pass_obj
def kg(obj, upstream):    
    if upstream is None:
        oda_sparql_root = os.getenv('ODA_SPARQL_ROOT', None)
        if oda_sparql_root is None:
            upstream = "file://" + os.getenv('HOME') + "/.kg"
        else:
            upstream = oda_sparql_root

    obj.upstream = upstream


def get_project_uri(project_path: Optional[str]=None) -> str:
    if project_path is None:
        project_path = os.getcwd()

    project_url = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=project_path).decode().strip()

    if project_url.startswith("git@"):
        # could be other : in the URL, ignoring
        project_url = project_url.replace(":", "/").replace("git@", "http://")

    if project_url.startswith("https://"):                    
        project_url = project_url.replace("https://", "http://")

    return project_url


def nuri(t):
    if t.startswith('file://'):
        local_project_path, run_id = t.split("/.renku/")
        local_project_path = local_project_path.replace("file://", "")

        project_url = get_project_uri(local_project_path)
        
        t = project_url + "#" + run_id

        
    return odakb.sparql.nuri(t) 


def normalize_local_graph(g):
    # replace references to local files with their URI
    nG = rdflib.Graph()

    # align with other place where is this
    nG.bind("oda", "http://odahub.io/ontology#")  
    nG.bind("odas", "https://odahub.io/ontology#")   # the same


    for t in g:
        _q = "{} {} {}\n".format(*[nuri(_t) for _t in t])            
        nG.update(f"INSERT DATA {{ {_q} }}")

    for rule in rules:
        rule(nG)
    
    return nG


def build_time_references(G, now_isot):
    # alternatively, can grade shapes with measurable predicates

    now_term = rdflib.URIRef("http://odahub.io/ontology#Now")
    
    for t in G.triples((None, None, rdflib.URIRef("http://odahub.io/ontology#TimeInstant"))):
        if t[0] == now_term:
            continue

        try:
            t_isot = str(list(G.triples((t[0], rdflib.URIRef('http://odahub.io/ontology#isot'), None)))[0][2])
        except:
            raise
            continue

        isot_format = '%Y-%m-%dT%H:%M:%S'

        month_sep = ((time.mktime(time.strptime(now_isot, isot_format)) - time.mktime(time.strptime(t_isot, isot_format)))/24/3600/30)

        distance = month_sep**2

        distance_term = rdflib.URIRef(f"http://odahub.io/ontology#distance{distance:7.5f}")

        # property graph lacking
        G.add((
                now_term,
                distance_term,
                t[0]
            ))

        G.add((
                distance_term,
                rdflib.URIRef(f"http://odahub.io/ontology#distance_term"),
                rdflib.term.Literal(distance)
            ))            


def trace_graph(W1, W2, G, trace):
    if ' ' in W1 or ' ' in W2:
        return []

    W1 = rdflib.URIRef(W1)
    W2 = rdflib.URIRef(W2)

    if W1 in trace:
        return []
    
    if W1 == W2:
        return [trace + [W2]]

    traces = [] 
    
    for s, p, o in G.triples((rdflib.URIRef(W1), None, None)):
        traces += trace_graph(o, W2, G, trace + [s, p]) 
        
    return traces

term_distances = yaml.load(open(Path(os.getenv("HOME")) / "term-distance.yaml"))

def term_distance(term: rdflib.URIRef, G: rdflib.Graph) -> float:
    # since even triangle relation is not guaranteed, may need more complex than sum
    # maybe better by introducing additional links

    if term.startswith('http://odahub.io/ontology#distance'):
        return sum([float(d[2]) for d in G.triples((term, rdflib.URIRef('http://odahub.io/ontology#distance_term'), None))])

    return term_distances.get(str(term), 1)


def develop_rank_relations(W1, W2, G, 
                           mode='resistor', 
                           add_distance_predicates=False, 
                           explain=False,
                           leave_only_distance=False
                           ) -> Tuple[float, rdflib.Graph]:
    # make reverse relations
    # like resistance. or lightning
    # loopy diagram strcuture?
    # node neigh as of

    iG = rdflib.Graph()
    iG.parse(data=G.serialize(format='n3'), format="n3")
    assign_default_bindings(iG)

    for s, p, o in iG.query(f'''SELECT ?s ?p ?o WHERE {{
                  ?s ?p ?o . 
                }}'''):
        iG.add((o, rdflib.URIRef(str(p) + "_inverse"), s))

    traces = trace_graph(W1, W2, iG, [])

    # remove inverse

    for s, p, o in iG:
        if str(p).endswith('_inverse'):
            iG.remove((s, p, o ))

    #TODO: draw links

    flow_predicate_uri = rdflib.URIRef('http://odahub.io/ontology#flow')

    total_distance = 1e100 # large resistor
    for trace in traces:
        if explain:
            click.echo("\033[31mtraced:\033[0m")
        trace_distance = 0
        for i, term in enumerate(trace):
            distance = term_distance(term, iG)
            trace_distance += distance

            if explain:
                click.echo(f"    {term.n3(G.namespace_manager):50s} {distance:10.5f}  {str(term):.100s}")        

            if add_distance_predicates:
                if i>0 and i<len(trace)-1:
                    deinv_term = rdflib.URIRef(str(term).replace('_inverse', ''))
                    if len(list(iG.triples((None, deinv_term, None)))) > 0:
                        iG.add((trace[i-1], flow_predicate_uri, trace[i+1]))
                        #iG.add((deinv_term, rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'), distance_predicate_uri))

        if explain:
            print(f"\033[33mtrace distance: {trace_distance}\033[0m\n")

        if mode == 'resistor':
            total_distance = 1 / (1/total_distance + 1/trace_distance) # resistor
        else:
            total_distance = min(total_distance, trace_distance)

    if explain:
        print(f"\033[31mtotal distance: {total_distance}\033[0m")


    nG = rdflib.Graph()
    assign_default_bindings(nG)

    if leave_only_distance:
        for s, p, o in iG:
            if len(list(iG.triples((s, flow_predicate_uri, o)))) > 0 or len(list(iG.triples((o, flow_predicate_uri, s)))):
                if p != flow_predicate_uri:
                    nG.add((s, p, o))

        iG = nG


    return total_distance, iG

    
    
@kg.command()
@click.pass_obj
def push(obj):
    graph = _graph("HEAD", [])

    # TODO: learn inputs here!
    # TODO: push and search  for CC workflows

    g = extract_aq_subgraph(graph)

    workflow = get_project_uri()
    learn_repo_workflow(workflow, g)

    if obj.upstream.startswith("file://"):
        fn = obj.upstream.replace("file://", "")
        G = rdflib.Graph()

        if os.path.exists(fn):
            print("found upstream KG:", fn)
            with open(fn) as f:
                G.parse(data=f.read(), format="n3")
        else:
            print("not yet found upstream KG:", fn)

        G.parse(data=g.serialize(format="n3"), format="n3")

        serial = G.serialize(format="n3")
        
        if isinstance(serial, bytes):
            serial = serial.decode()
        
        print(serial)

        with open(fn, "w") as f:
            f.write(serial)

    elif obj.upstream.startswith("https://"):
        tuples = ""
        for t in g:
            tuples += "\n{} {} {} .".format(*map(nuri, t))
        
        odakb.sparql.insert(tuples)


def node_distance(W1, W2, context):
    # todo make as a rule

    # distances are similar to those found in NLP, associations and similarity (see UNIGE DS talk 211111)
    
    #    return 1 - (time.time() - time.mktime(time.strptime(input[3:9], "%y%m%d")))/(24*3600*30)

    #   d = odakb.sparql.select('?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object')

    # use source name distance
    # use source class. find in simbad

    # TODO: give suggestions for calls within workflow
    # TODO: push CC, integral transient
    # TODO: not just MM, project domain

    return 1


def rule_infer_inputs(G):    
    for l in G.query('SELECT * WHERE {?run oda:isRequestingAstroObject ?obj}'): 
        # this is not necessarily true, but will be applicable until we understand plan situation and make ontology of inputs

        obj = l['obj']
        run = l['run']
        wfl, run_id = run.split("#")

        r = f'''
                <{run}> a oda:Run .
            '''

        # TODO: this should be determined from inspecting notebook for parameters
        r += f'''
                <{wfl}> a oda:Workflow;
                        oda:has_input_binding oda:has_input_source_name .
                        
                oda:has_input_source_name a oda:input_binding_predicate;
                                          oda:input_type oda:AstrophysicalObject .
            '''

        # TODO: deduce more generally 
        r += f'''
                <{wfl}> oda:has_runs_with_astro_object <{obj}> .
            '''


        print(f"\033[32m {r}\033[0m")

        G.update(f'INSERT DATA {{ {r} }}')

# should be in shacl but this is faster. pyshacl
rules = [rule_infer_inputs]


def learn_repo_workflow(wfl, G):
    notebooks = glob.glob("*.ipynb")    

    if len(notebooks) == 1:
        notebook = notebooks[0]
    else:
        try:
            notebook = yaml.load(open('oda.yaml'))['root_notebook']
        except FileNotFoundError:
            raise NotImplementedError


    nbsig = NotebookAdapter(notebook).extract_parameters()

    print(nbsig)

    for k, v in nbsig.items():
        r = f'''
                <{wfl}> oda:has_input_binding oda:has_input_{k} .
                        
                oda:has_input_{k} a oda:input_{k};
                                  oda:input_type <{v['owl_type']}> .
            '''

        def normalize_to_term(value):
            return re.sub("[^a-zA-Z0-8\.]", "", value)



        # learn about new odahub entity?
        if 'odahub.io' in v['owl_type']:
            term = rdflib.URIRef('http://odahub.io/ontology/values#'+normalize_to_term(v['value']))

            print(term)

            r += f'''
                {term.n3()} a <{v['owl_type']}>;
                                                                                   rdfs:label "{v['value']}" .
            '''

            # TODO: expand graph (could be done generally)

            r0 = odakb.sparql.construct(f'{term.n3()} ?y ?z . ?z ?a ?b', jsonld=False)
            # r1 = odakb.sparql.construct(f'{term.n3()} ?y ?z . ?z ?a ?b . ?b ?w ?e', jsonld=False)
            iG = rdflib.Graph()
            iG.parse(data=r0, format='turtle')
            # iG.parse(data=r1, format='turtle')

            for s, p, o in iG:
                r += f'''
                    {s.n3()} {p.n3()} {o.n3()} .
                '''
            # r1 = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z .', jsonld=False)



        print(r)
         
        G.update(f'INSERT DATA {{ {r} }}')


@kg.command()
@click.option('--ignore-now', is_flag=True, default=False)
@click.option('--explain', is_flag=True, default=False)
@click.option('--plot', is_flag=True, default=False)
@click.option('--plot-distance', is_flag=True, default=False)
@click.option('--plot-only-distance', is_flag=True, default=False)
@click.option('--learn-inputs', is_flag=True, default=False)
@click.option('--max-options', default=10, type=float)
@click.option('--filter-input-value', default=None, type=str)
@click.pass_obj
def suggest(obj, explain, ignore_now, plot, plot_distance, plot_only_distance, learn_inputs, max_options, filter_input_value):
    # this implements https://github.com/oda-hub/smartsky/issues/25
    # TODO: for better association and scoring see https://github.com/oda-hub/smartsky/issues/25
    
    if plot_only_distance:
        plot_distance = True
        

    graph = _graph("HEAD", [])
    local_graph = extract_aq_subgraph(graph)

    
    if obj.upstream.startswith("https://"):
        import odakb.sparql        

        normal_local_graph = normalize_local_graph(local_graph)
        
        workflow = get_project_uri()

        # construct current context from current directory, current time
        # 1. find all inputs for this workflow. combine with them to produce planned run. 
        # 2. find all workflow runs
        # 3. find all workflows and combine with all inputs producing plans

        print("W1 (current renku/gitlab project):", workflow)

        focus = "http://odahub.io/ontology#Focus"
        W1 = focus

        # TODO: collect inputs here
        normal_local_graph.update(f'''
            INSERT DATA {{
                    <{focus}> oda:relatedTo <{workflow}> .
            }}''')
        
        # perhaps detect notebook in oda.yaml
        if learn_inputs:
            learn_repo_workflow(workflow, normal_local_graph)

        if not ignore_now:
            now_isot = time.strftime("%Y-%m-%dT%H:%M:%S")
            normal_local_graph.update(f'''
                INSERT DATA {{
                        <{focus}> oda:event_time oda:Now .

                        oda:Now oda:isot "{now_isot}";
                                a oda:TimeInstant .
                }}''')

        output = PrettyTable()
        output.field_names = ["Workflow", "Inputs", "Distance"]        

        n_entries = 0

        for input_binding_struct in normal_local_graph.query(f'''
                        SELECT * WHERE {{ 
                            <{workflow}> oda:has_input_binding ?input_binding_predicate .

                            OPTIONAL {{
                                <{workflow}> ?input_binding_predicate ?input_value .
                            }}
                                   
                            ?input_binding_predicate oda:input_type ?input_type .
                        }} LIMIT 5
                    '''):

            input_type = input_binding_struct["input_type"]

            #print("found input", input_binding_struct)
            # this is incomplete somehow            
            r = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z . ?z ?a ?b', jsonld=False)
            r1 = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z .', jsonld=False)


            # GG = rdflib.Graph()
            # GG.parse(odakb.sparql.discover_oda_sparql_root(None), format='turtle')
            # r = GG.query(f'CONSTRUCT WHERE {{ ?x a <{input_type}>; ?y ?z . ?o ?a ?b }}')

            # r = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z .', jsonld=False)

            #print("\033[31m", r, "\033[0m")
            with open("context.ttl", "w") as f:
                f.write(r)

            iG = rdflib.Graph()
            iG.parse(data=r, format='turtle')
            iG.parse(data=r1, format='turtle')

            #print(list(iG.query('SELECT * WHERE { ?a ?b oda:TimeInstant }')))

            # return

            # try to derive relevance before selecting, to deal with less inputs
            for input_value, in iG.query(f'SELECT * WHERE {{?x a <{input_type}>}}'):
                # here we construct sufficient graph to compute distances
                # print("input option row", input_value)

                # input_value = "http://odahub.io/ontology#AstroObjectMrk_421"

                # TODO: select by scope/domain/affinity
                # if "Mrk" not in str(input_value): continue
                #if "GRB200623A" not in str(input_value): continue

                if filter_input_value is not None:
                    if not re.search(filter_input_value, input_value):
                        continue
                
                tiG = rdflib.Graph()
                assign_default_bindings(tiG)

                # absorb details about inputs (one level link depth only for now)
                for t in list(iG.query(f'CONSTRUCT WHERE {{<{input_value}> ?p ?o . ?o ?a ?b}}')) + \
                         list(iG.query(f'CONSTRUCT WHERE {{<{input_value}> ?p ?o .}}')):
                    tiG.add(t)
                    

                tiG.parse(data=normal_local_graph.serialize(format='turtle'))


                # construct plan (possible run)
                W2 = f"{workflow}/Plan"
                tiG.update(f"""
                    INSERT DATA {{
                        <{W2}> a oda:Plan;
                             <{input_binding_struct["input_binding_predicate"]}> <{input_value}> .
                    }}
                """)

                if not ignore_now:
                    build_time_references(tiG, now_isot)

                distance, ciG = develop_rank_relations(W1, W2, tiG, add_distance_predicates=plot_distance, explain=explain, leave_only_distance=plot_only_distance)
                

                #print("\033[35mlocal_graph with plan:","\n" + tiG.serialize(format='ttl'), "\033[0m")

                if plot:
                    plot_graph(ciG, "graph.svg")
                
                print(f"\033[31mtotal distance: {distance}\033[0m", input_value)

                output.add_row([workflow, input_value, distance])

                n_entries += 1

                if n_entries >= max_options:
                    break
            
        output.sortby = 'Distance'
        output.reversesort = True
            
        print(output)
        
        # output = PrettyTable()
        # output.field_names = ["Workflow", "Astro Object", "Score"]
        # output.align["Run"] = "l"

        # for r in d:            
        #     workflow = r['run'].split(".renku")[0]
        #     print(r['run'], workflow, r['a_object'])
        #     q = f"<{r['a_object']}> ?p ?o"
        #     print("about object:", q)
        #     output.add_row([workflow, r['a_object'], 1.0])
        
        # D = odakb.sparql.query(
        #     '''
        #     PREFIX paper: <http://odahub.io/ontology/paper#>
        #     SELECT * WHERE {
        #         ?paper paper:mentions_named_grb ?name; 
        #                paper:grb_isot ?isot .
        #     }
        #     ORDER BY DESC(?isot)
        #     LIMIT 100''', 
        # )
        
        # D = {
        #             d['name']['value']: {
        #                 'isot': d['isot']['value'],
        #             }
        #         for d in D['results']['bindings']}

        # for k, v in list(D.items())[:10]:                        
        #     output.add_row(['', k, compute_local_score('', k)])
            
        # objects_of_interest = odakb.sparql.select(
        #     '''
        #     ?object an:name ?object_name; 
        #             an:importantIn ?domain;
        #             ?p ?o .
        #     ''',          
        #     '?object ?p ?o',  
        #     tojdict=True,
        #     limit=100)        

        
        # source_list = list([v['an:name'][0] for k, v in objects_of_interest.items()])
        # for source in source_list:
        #     output.add_row(['', source, compute_local_score('', source)])

        # print("\033[31mtry other objects for this workflow\033[0m")
        # print(output)
