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
import time
import json
from typing import DefaultDict, Optional
import click
import rdflib
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

def plot_graph(G, filename="graph.svg"):
    stream = io.StringIO()

    # def color(p, placement='predicate'):
    #     if placement == 'predicate':
    #         print("coloring:", p)
    #         return "RED"

    #     elif placement == 'bgcolor':
    #         print("coloring:", p)
    #         return "blue"

    #     elif placement == 'node_label':
    #         if 'focus' in p:
    #             return 'lightgreen'
    #         else:
    #             return 'grey'
        

    rdf2dot.rdf2dot(G, stream, opts={})    

    dot_data = stream.getvalue()

    with open(filename.replace('.svg', '.dot'), "w") as f:
        f.write(dot_data)

    pydotplus.graph_from_dot_data(dot_data).write_svg(filename)

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
    
    print(serial)

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


def build_time_references(G):
    time_triples = G.query('SELECT * WHERE {?time a oda:TimeInstant; oda:isot ?isot}')

    for t in time_triples:
        pass
        # print(t)

def develop_rank_relations(W1, W2, G):
    # make reverse relations
    iG = rdflib.Graph()
    iG.parse(data=G.serialize(format='n3'), format="n3")

    for s, p, o in iG.query(f'''SELECT ?s ?p ?o WHERE {{
                  ?s ?p ?o . 
                }}'''):
        iG.add((o, rdflib.URIRef(str(p) + "_anti"), s))
        

    #for r in iG.query(f'''SELECT ?p1 ?o1 ?p2 ?o2 WHERE {{


    triples = [f'?s{i} ?p{i} ?o{i}' for i in range(5)]
    
    x = ' '.join(triples)
    y = "\n".join([t + " ." for t in triples])

    y = y.replace('?s0', f'<{W1}>')
    y = y.replace('?s4', f'<{W2}>')

    q = f'''SELECT {x} WHERE {{
                   {y}
                  
                    FILTER (
                        (?o0 = ?s1) && (?o1 = ?s2) && (?o2 = ?s3) && (?o3 = ?s4)
                  )                   
                }}'''
                

    print(q)

    for r in iG.query(q):        
        eG = rdflib.Graph()
        eG.add((rdflib.URIRef(W1), r[0], r[1]))
        eG.add((rdflib.URIRef(W2), r[2], r[3]))
        eG.add((r[4], r[5], r[6]))

        print("\033[31mrelation", W1, W2, "\033[0m")

        assign_default_bindings(eG)
        print(eG.serialize(format='turtle'))

@kg.command()
@click.pass_obj
def push(obj):
    graph = _graph("HEAD", [])

    g = extract_aq_subgraph(graph)

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

    return 1


def rule_infer_inputs(G):    
    print(">>rule_infer_inputs")
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

@kg.command()
@click.pass_obj
def suggest(obj):
    # this implements https://github.com/oda-hub/smartsky/issues/25
    # TODO: for better association and scoring see https://github.com/oda-hub/smartsky/issues/25
    
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

        focus = "http://odahub.io/ontology#focus"
        W1 = focus

        now_isot = time.strftime("%Y-%m-%dT%H:%M:%S")

        normal_local_graph.update(f'''
            INSERT DATA {{
                    <{focus}> oda:event_time oda:Now;
                              oda:relatedTo <{workflow}> .
                    oda:Now oda:isot "{now_isot}";
                            a oda:TimeInstant .
            }}''')

        
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

            print("found input", input_binding_struct)
            # r = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z . ?z a ?b', jsonld=False)
            r = odakb.sparql.construct(f'?x a <{input_type}>; ?y ?z . ?z ?a ?b', jsonld=False)

            print("\033[31m", r, "\033[0m")

            iG = rdflib.Graph()
            iG.parse(data=r, format='turtle')

            #print(list(iG.query('SELECT * WHERE { ?a ?b oda:TimeInstant }')))

            # return

            for input_value, in iG.query(f'SELECT * WHERE {{?x a <{input_type}>}}'):
                # here we construct sufficient graph to compute distances
                print("input option row", input_value)

                input_value = "http://odahub.io/ontology#AstroObjectMrk_421"

                # TODO: select by scope/domain/affinity
                # if "Mrk" not in str(input_value): continue
                # if "GRB200623A" not in str(input_value): continue
                
                tiG = rdflib.Graph()
                assign_default_bindings(tiG)

                # absorb details about inputs (one level link depth only for now)
                for t in list(iG.query(f'CONSTRUCT WHERE {{<{input_value}> ?p ?o . ?o ?a ?b}}')) + \
                         list(iG.query(f'CONSTRUCT WHERE {{<{input_value}> ?p ?o .}}')):
                    tiG.add(t)
                    

                tiG.parse(data=normal_local_graph.serialize(format='turtle'))


                # construct plan (possible run)
                W2 = f"{workflow}/plan"
                tiG.update(f"""
                    INSERT DATA {{
                        <{W2}> a oda:Plan;
                             <{input_binding_struct["input_binding_predicate"]}> <{input_value}> .
                    }}
                """)

                build_time_references(tiG)

                develop_rank_relations(W1, W2, tiG)
                

                print("\033[35mlocal_graph with plan:","\n" + tiG.serialize(format='ttl'), "\033[0m")

                plot_graph(tiG)
                
                break

            
            # for k, v in input_options.items():
            #     print(k, v)

        # for run in local_graph.query('SELECT * WHERE {?r a oda:Run}'):
        #     print("run", run)

        
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
