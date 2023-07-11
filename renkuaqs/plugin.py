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
import re
import subprocess
import webbrowser
import click
import rdflib
import rdflib.tools.rdf2dot

from pathlib import Path
from renku.domain_model.provenance.annotation import Annotation
from renku.domain_model.project_context import project_context
from renku.core.plugin import hookimpl
from IPython.display import Image, HTML
from prettytable import PrettyTable
from aqsconverters.io import AQS_ANNOTATION_DIR, COMMON_DIR
from renkuaqs.config import ENTITY_METADATA_AQS_DIR
from nb2workflow import ontology

import renkuaqs.graph_utils as graph_utils


class AQS(object):
    def __init__(self, run):
        self.run = run

    @property
    def renku_aqs_path(self):
        """Return a ``Path`` instance of Renku AQS metadata folder."""
        return Path(project_context.metadata_path).joinpath(AQS_ANNOTATION_DIR).joinpath(COMMON_DIR)

    @property
    def aqs_annotation_path(self):
        """Return a ``Path`` instance of Renku AQS specific annotation."""
        return Path(ENTITY_METADATA_AQS_DIR)

    def load_model(self, path):
        """Load AQS reference file."""
        if path and path.exists():
            return json.load(path.open())
        return {}


@hookimpl
def plan_annotations(plan):
    print(f"plan_annotations, plan \033[31m{plan.name}\033[0m")

    annotations = []

    return annotations


@hookimpl
def activity_annotations(activity):
    """``process_run_annotations`` hook implementation."""
    aqs = AQS(activity)

    sitecustomize_path = pathlib.Path(os.path.join(project_context.metadata_path, AQS_ANNOTATION_DIR, "sitecustomize.py"))
    if sitecustomize_path.exists():
        sitecustomize_path.unlink()

    annotations = []

    print("process_run_annotations")
    print(aqs.renku_aqs_path)
    # apply nb2rdf also to input nb and also add the name of the notebook
    # should be related to the input/output notebook
    # add the annotations to the plan

    if activity.generations is not None and len(activity.generations) >= 1:
        for generation in activity.generations:
            entity = generation.entity
            if isinstance(entity, list):
                entity = generation.entity[0]
            entity_file_name, entity_file_extension = os.path.splitext(entity.path)
            if entity_file_extension == '.ipynb':
                print(f"\033[31mExtracting metadata from the output notebook: {entity.path}, id: {entity.id}\033[0m")
                rdf_nb = ontology.nb2rdf(entity.path)
                print(f"\033[32m{rdf_nb}\033[0m")
                G = rdflib.Graph()
                G.parse(data=rdf_nb)
                rdf_jsonld_str = G.serialize(format="json-ld")
                rdf_jsonld = json.loads(rdf_jsonld_str)
                for nb2annotation in rdf_jsonld:
                    # to comply with the terminology
                    nb2annotation["http://odahub.io/ontology#entity_checksum"] = entity.checksum
                    print(f"found jsonLD annotation:\n", json.dumps(nb2annotation, sort_keys=True, indent=4))
                    model_id = nb2annotation["@id"]
                    annotation_id = "{activity}/annotations/aqs/{id}".format(
                        activity=activity.id, id=model_id
                    )
                    annotations.append(
                        Annotation(id=annotation_id, source="AQS plugin", body=nb2annotation)
                    )

    if os.path.exists(aqs.renku_aqs_path):
        for p in aqs.renku_aqs_path.iterdir():
            if p.match("*json"):
                print(f"found json annotation: {p}")
                print(open(p).read())

            elif p.match("*jsonld"):
                aqs_annotation = aqs.load_model(p)
                print(f"found jsonLD annotation: {p}\n", json.dumps(aqs_annotation, sort_keys=True, indent=4))

                # this will make annotations according to https://odahub.io/ontology/
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
    print(f"\033[31mhere we will prepare hooks for astroquery, tool given is {tool}\033[0m")

    sitecustomize_dir = Path(project_context.metadata_path, AQS_ANNOTATION_DIR)

    if not sitecustomize_dir.exists():
        sitecustomize_dir.mkdir(parents=True)

    os.environ["PYTHONPATH"] = f"{sitecustomize_dir}:" + os.environ.get('PYTHONPATH', "")

    sitecustomize_path = os.path.join(sitecustomize_dir, "sitecustomize.py")

    print(f"\033[34msitecustomize.py as {sitecustomize_path}\033[0m")

    open(sitecustomize_path, "w").write("""
print(f"\033[31menabling hooks for astroquery\033[0m")  

import aqsconverters.aq

aqsconverters.aq.autolog()
""")


def _run_id(activity_id):
    return str(activity_id).split("/")[-1]


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
    graph = graph_utils._graph(revision, paths)
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

    graph = graph_utils._graph(revision, paths)

    renku_path = project_context.path

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
    G.bind("odas", "https://odahub.io/ontology#")  # the same
    G.bind("local-renku", f"file://{renku_path}/")  # ??


def show_graph_image(revision="HEAD", paths=os.getcwd(), filename="graph.png", no_oda_info=True, input_notebook=None):
    filename = graph_utils.build_graph_image(revision, paths, filename, no_oda_info, input_notebook)
    return Image(filename=filename)


@aqs.command()
@click.option(
    "--revision",
    default="HEAD",
    help="The git revision to generate the log for, default: HEAD",
)
@click.option("--input-notebook", default=None, help="Input notebook to process")
@click.argument("paths", type=click.Path(exists=False), nargs=-1)
def inspect(revision, paths, input_notebook):
    """Inspect the input entities within the graph"""

    path = paths
    if paths is not None and isinstance(paths, click.Path):
        path = str(path)

    graph_utils.inspect_oda_graph_inputs(revision, path, input_notebook)

    return ""


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
    path = paths
    if paths is not None and isinstance(paths, click.Path):
        path = str(path)
    output_filename = graph_utils.build_graph_image(revision, path, filename, no_oda_info, input_notebook)
    return output_filename


@aqs.command()
def start_session():
    gitlab_url = subprocess.check_output(["git", "remote", "get-url", "origin"]).decode().strip()

    new_session_urls = []

    for pattern in [
        'https://renkulab.io/gitlab/(.*)\.git',
        'git@renkulab.io:(.*)\.git'
    ]:
        if (r := re.match(pattern, gitlab_url)) is not None:
            new_session_urls.append(f"https://renkulab.io/projects/{r.group(1)}/sessions/new?autostart=1&branch=master")

    if (n := len(new_session_urls)) > 1:
        click.echo(f"using first of many session URLs: {new_session_urls}")
    elif n == 0:
        raise RuntimeError("unable to find any session URLs")

    click.echo(f"will open new session: {new_session_urls[0]}")

    webbrowser.open(new_session_urls[0])


@aqs.command()
def show_graph():
    graph_html_content, ttl_content = graph_utils.build_graph_html(None, None)
    html_fn, ttl_fn = graph_utils.write_graph_files(graph_html_content, ttl_content)

    webbrowser.open(html_fn)


def build_graph(paths=os.getcwd(), template_location="local"):
    graph_html_content, ttl_content = graph_utils.build_graph_html(None, paths, template_location=template_location)
    graph_utils.write_graph_files(graph_html_content, ttl_content)


def display_interactive_graph(revision="HEAD", paths=os.getcwd(), include_title=False):
    graph_html_content, ttl_content = graph_utils.build_graph_html(None, paths, include_title=include_title)
    html_fn, ttl_fn = graph_utils.write_graph_files(graph_html_content, ttl_content)

    return HTML(f"""
        <iframe width="100%" height="1150px", src="{html_fn}" frameBorder="0" scrolling="no">
        </iframe>"""
                )
