import os
import io
import typing
import pydotplus
import rdflib
import yaml
import json

from rdflib.tools.rdf2dot import LABEL_PROPERTIES
from rdflib.tools import rdf2dot
from lxml import etree
from dateutil import parser
from astropy.coordinates import SkyCoord, Angle
from IPython.display import display
from pyvis.network import Network
from importlib import resources

from renku.domain_model.project_context import project_context
from renku.command.graph import export_graph_command
from renku.core.errors import RenkuException

import renkuaqs.javascript_graph_utils as javascript_graph_utils

# TODO improve this
__this_dir__ = os.path.join(os.path.abspath(os.path.dirname(__file__)))
graph_configuration = yaml.load(open(os.path.join(__this_dir__, "graph_config.yaml")), Loader=yaml.SafeLoader)


def _graph(revision=None, paths=None):
    # FIXME: use (revision) filter

    cmd_result = export_graph_command().working_directory(paths).build().execute()

    if cmd_result.status == cmd_result.FAILURE:
        raise RenkuException("fail to export the renku graph")
    graph = cmd_result.output.as_rdflib_graph()

    graph.bind("aqs", "http://www.w3.org/ns/aqs#")
    graph.bind("oa", "http://www.w3.org/ns/oa#")
    graph.bind("xsd", "http://www.w3.org/2001/XAQSchema#")
    graph.bind("oda", "http://odahub.io/ontology#")
    graph.bind("odas", "https://odahub.io/ontology#")
    graph.bind("local-renku", f"file://{paths}/")

    return graph


def build_graph_html(revision, paths, include_title=True, template_location="local"):

    if paths is None:
        paths = project_context.path

    graph = _graph(revision, paths)

    graph_str = graph.serialize(format="n3")

    with open('full_graph.ttl', 'w') as gfn:
        gfn.write(graph_str)

    full_graph_ttl_str = graph_str.replace("\\\"", '\\\\"')

    # # TODO to be tested
    # with resources.path("renkuaqs", 'oda_ontology.ttl') as ttl_ontology_fn:
    #     graph = graph.parse(source=ttl_ontology_fn)

    html_fn = 'graph.html'
    default_graph_graphical_config_fn = 'graph_graphical_config.json'
    graph_nodes_subset_config_fn = 'graph_nodes_subset_config.json'
    graph_reduction_config_fn = 'graph_reduction_config.json'
    nodes_graph_config_obj = {}
    edges_graph_config_obj = {}

    graph_config_names_list = []
    with resources.open_text("renkuaqs", default_graph_graphical_config_fn) as graph_config_fn_f:
        graph_config_loaded = json.load(graph_config_fn_f)
        nodes_graph_config_obj_loaded = graph_config_loaded.get('Nodes', {})
        edges_graph_config_obj_loaded = graph_config_loaded.get('Edges', {})

    if nodes_graph_config_obj_loaded:
        for config_type in nodes_graph_config_obj_loaded:
            nodes_graph_config_obj_loaded[config_type]['config_file'] = default_graph_graphical_config_fn
        nodes_graph_config_obj.update(nodes_graph_config_obj_loaded)
    if edges_graph_config_obj_loaded:
        for config_type in edges_graph_config_obj_loaded:
            edges_graph_config_obj_loaded[config_type]['config_file'] = default_graph_graphical_config_fn
        edges_graph_config_obj.update(edges_graph_config_obj_loaded)
    graph_config_names_list.append(default_graph_graphical_config_fn)
    # for compatibility with Javascript
    nodes_graph_config_obj_str = json.dumps(nodes_graph_config_obj)
    edges_graph_config_obj_str = json.dumps(edges_graph_config_obj)

    with resources.open_text("renkuaqs", graph_reduction_config_fn) as graph_reduction_config_fn_f:
        graph_reduction_config_obj = json.load(graph_reduction_config_fn_f)

    # for compatibility with Javascript
    graph_reductions_obj_str = json.dumps(graph_reduction_config_obj)

    with resources.open_text("renkuaqs", graph_nodes_subset_config_fn) as graph_nodes_subset_config_fn_f:
        graph_nodes_subset_config_obj = json.load(graph_nodes_subset_config_fn_f)

    # for compatibility with Javascript
    graph_nodes_subset_config_obj_str = json.dumps(graph_nodes_subset_config_obj).replace("\\\"", '\\\\"').replace("\\n", '\\\\n')

    net = Network(
        height='750px', width='100%',
        cdn_resources=template_location
    )
    net.generate_html(html_fn)

    javascript_graph_utils.set_html_head(net)

    javascript_graph_utils.add_js_click_functionality(net,
                                                      graph_ttl_stream=full_graph_ttl_str,
                                                      nodes_graph_config_obj_str=nodes_graph_config_obj_str,
                                                      edges_graph_config_obj_str=edges_graph_config_obj_str,
                                                      graph_reductions_obj_str=graph_reductions_obj_str,
                                                      graph_nodes_subset_config_obj_str=graph_nodes_subset_config_obj_str)

    javascript_graph_utils.set_html_content(net,
                                            graph_config_names_list=graph_config_names_list,
                                            nodes_graph_config_obj_dict=nodes_graph_config_obj,
                                            edges_graph_config_obj_dict=edges_graph_config_obj,
                                            graph_reduction_config_obj_dict=graph_reduction_config_obj,
                                            graph_nodes_subset_config_obj_dict=graph_nodes_subset_config_obj,
                                            include_title=include_title)

    javascript_graph_utils.write_modified_html_content(net, html_fn)

    return net, html_fn


def build_graph_image(revision, paths, filename, no_oda_info, input_notebook):
    """Simple graph visualization """

    if paths is None:
        paths = project_context.path

    graph = _graph(revision, paths)
    renku_path = paths

    query_where = build_query_where(input_notebook=input_notebook, no_oda_info=no_oda_info)
    query_construct = build_query_construct(no_oda_info=no_oda_info)

    query = f"""{query_construct}
               {query_where}
               """

    r = graph.query(query)

    G = rdflib.Graph()
    G.parse(data=r.serialize(format="n3").decode(), format="n3")
    G.bind("oda", "http://odahub.io/ontology#")
    G.bind("odas", "https://odahub.io/ontology#")  # the same
    G.bind("local-renku", f"file://{renku_path}/")

    extract_activity_start_time(G)

    if not no_oda_info:
        # process oda-related information (eg do the inferring)
        process_oda_info(G)

    action_node_dict = {}
    type_label_values_dict = {}
    args_default_value_dict = {}
    out_default_value_dict = {}

    analyze_inputs(G)
    analyze_arguments(G, action_node_dict, args_default_value_dict)
    analyze_outputs(G, out_default_value_dict)
    analyze_types(G, type_label_values_dict)

    clean_graph(G)

    stream = io.StringIO()
    rdf2dot.rdf2dot(G, stream, opts={display})
    pydot_graph = pydotplus.graph_from_dot_data(stream.getvalue())

    for node in pydot_graph.get_nodes():
        customize_node(node,
                       graph_configuration,
                       type_label_values_dict=type_label_values_dict
                       )

    # list of edges and simple color change
    for edge in pydot_graph.get_edge_list():
        customize_edge(edge)

    # final output write over the png image
    pydot_graph.write_png(filename)

    return filename



def customize_edge(edge: typing.Union[pydotplus.Edge]):
    if 'label' in edge.obj_dict['attributes']:
        edge_html = etree.fromstring(edge.obj_dict['attributes']['label'][1:-1])
        # simple color code
        # those two are not relevant at the moment since new predicates have been infered
        # if edge_html.text == 'oda:isRequestingAstroObject':
        #     edge.obj_dict['attributes']['color'] = '#2986CC'
        # if edge_html.text == 'oda:isUsing':
        #     edge.obj_dict['attributes']['color'] = '#53D06A'
        # TODO remove first part of the label ?
        edge_html.text = edge_html.text.split(":")[1]
        edge.set_label('< ' + etree.tostring(edge_html, encoding='unicode') + ' >')


def get_edge_label(edge: typing.Union[pydotplus.Edge]) -> str:
    edge_label = None
    if 'label' in edge.obj_dict['attributes']:
        edge_html = etree.fromstring(edge.obj_dict['attributes']['label'][1:-1])
        edge_label_list = edge_html.text.split(":")
        if len(edge_label_list) == 1:
            edge_label = edge_html.text.split(":")[0]
        else:
            edge_label = edge_html.text.split(":")[1]
    return edge_label


def get_id_node(node: typing.Union[pydotplus.Node]) -> str:
    id_node = None
    if 'label' in node.obj_dict['attributes']:
        table_html = etree.fromstring(node.get_label()[1:-1])
        tr_list = table_html.findall('tr')

        td_list_first_row = tr_list[0].findall('td')
        if td_list_first_row is not None:
            b_element_title = td_list_first_row[0].findall('B')
            if b_element_title is not None:
                id_node = b_element_title[0].text

    return id_node


def get_node_graphical_info(node: typing.Union[pydotplus.Node],
                   type_node) -> [str, str]:
    node_label = ""
    node_title = ""
    if 'label' in node.obj_dict['attributes']:
        # parse the whole node table into a lxml object
        table_html = etree.fromstring(node.get_label()[1:-1])
        tr_list = table_html.findall('tr')
        for tr in tr_list:
            list_td = tr.findall('td')
            if len(list_td) == 2:
                list_left_column_element = list_td[0].text.split(':')
                # setting label
                if type_node == 'Action':
                    if 'command' in list_left_column_element:
                        node_label = '<b>' + list_td[1].text[1:-1] + '</b>'
                elif type_node == 'CommandInput':
                    node_label = '<b><i>' + list_td[1].text[1:-1] + '</i></b>'
                else:
                    node_label = ('<b>' + type_node + '</b>\n' + list_td[1].text[1:-1])
                # setting title
                if 'startedAtTime' in list_left_column_element:
                    parsed_startedAt_time = parser.parse(list_td[1].text.replace('^^xsd:dateTime', '')[1:-1])
                    # create an additional row to attach at the bottom, so that time is always at the bottom
                    node_title += parsed_startedAt_time.strftime('%Y-%m-%d %H:%M:%S') + '\n'

    if node_label == "":
        node_label = '<b>' + type_node + '</b>'
    if node_title == "":
        node_title = type_node
    return node_label, node_title


def customize_node(node: typing.Union[pydotplus.Node],
                   graph_configuration,
                   type_label_values_dict=None,
                   ):
    id_node = None
    if 'label' in node.obj_dict['attributes']:
        # parse the whole node table into a lxml object
        table_html = etree.fromstring(node.get_label()[1:-1])
        tr_list = table_html.findall('tr')

        # modify the first row, hence the title of the node, and then all the rest
        td_list_first_row = tr_list[0].findall('td')
        if td_list_first_row is not None:
            td_list_first_row[0].attrib.pop('bgcolor')
            b_element_title = td_list_first_row[0].findall('B')
            if b_element_title is not None and b_element_title[0].text in type_label_values_dict:
                id_node = b_element_title[0].text
            if id_node is not None:
                # change title of the node
                if type_label_values_dict[b_element_title[0].text] != 'CommandParameter':
                    b_element_title[0].text = type_label_values_dict[b_element_title[0].text]
                if b_element_title[0].text.startswith('CommandOutput') and \
                        b_element_title[0].text != 'CommandOutput':
                    b_element_title[0].text = b_element_title[0].text[13:]
                # apply styles (shapes, colors etc etc)
                node_configuration = graph_configuration.get(type_label_values_dict[id_node],
                                                             graph_configuration['Default'])
                table_html.attrib['cellborder'] = str(node_configuration.get('cellborder',
                                                                             graph_configuration['Default']['cellborder'])
                                                      )
                table_html.attrib['border'] = str(node_configuration.get('border',
                                                                         graph_configuration['Default']['cellborder'])
                                                  )
                # color and shape change
                node.set_style(node_configuration['style'])
                node.set_shape(node_configuration['shape'])
                node.set_color(node_configuration['color'])
                # remove top row for some cells were this is not wanted
                display_top_row = bool(node_configuration.get('display_type_title',
                                                              graph_configuration['Default']['display_type_title'])
                                       )
                if not display_top_row:
                    table_html.remove(tr_list[0])
                # remove not needed long id information
                table_html.remove(tr_list[1])
                # remove not-needed information in the output tree nodes (eg defaultValue text, position value)
                for tr in tr_list:
                    list_td = tr.findall('td')
                    if len(list_td) == 2:
                        list_left_column_element = list_td[0].text.split(':')
                        # remove left side text (eg defaultValue)
                        tr.remove(list_td[0])
                        if 'align' in list_td[1].keys():
                            list_td[1].attrib['align'] = 'center'
                            list_td[1].attrib['colspan'] = '2'
                        # special case default_value table_row
                        if 'defaultValue' in list_left_column_element and \
                                type_label_values_dict[id_node] == 'CommandParameter':
                            list_args_commandParameter = list_td[1].text[1:-1].split(' ')
                            if b_element_title is not None and b_element_title[0].text in type_label_values_dict:
                                b_element_title[0].text = list_args_commandParameter[0]
                                list_td[1].text = '"' + ' '.join(list_args_commandParameter[1:]) + '"'
                        if 'startedAtTime' in list_left_column_element:
                            # TODO to improve and understand how to parse xsd:dateTime time
                            parsed_startedAt_time = parser.parse(list_td[1].text.replace('^^xsd:dateTime', '')[1:-1])
                            # create an additional row to attach at the bottom, so that time is always at the bottom
                            bottom_table_row = etree.Element('tr')
                            time_td = etree.Element('td')
                            time_td.attrib['align'] = 'center'
                            time_td.attrib['colspan'] = '2'
                            time_td.text = parsed_startedAt_time.strftime('%Y-%m-%d %H:%M:%S')
                            bottom_table_row.append(time_td)
                            tr.remove(list_td[1])
                            table_html.remove(tr)
                            table_html.append(bottom_table_row)

                        # remove trailing and leading double quotes
                        list_td[1].text = list_td[1].text[1:-1]
                        # bold text in case of action
                        if type_label_values_dict[id_node] == 'Action' and \
                                 'command' in list_left_column_element:
                            bold_text_element = etree.Element('B')
                            bold_text_element.text = list_td[1].text
                            list_td[1].append(bold_text_element)
                            list_td[1].text = ""
                        # italic ad bold in case of input
                        if type_label_values_dict[id_node] == 'CommandInput':
                            bold_text_element = etree.Element('B')
                            italic_text_element = etree.Element('I')
                            italic_text_element.text = list_td[1].text
                            bold_text_element.append(italic_text_element)
                            list_td[1].append(bold_text_element)
                            list_td[1].text = ""

            # serialize back the table html
            node.obj_dict['attributes']['label'] = '< ' + etree.tostring(table_html, encoding='unicode') + ' >'

def build_query_where(input_notebook: str = None, no_oda_info=False):
    if input_notebook is not None:
        query_where = f"""WHERE {{
            {{
                ?entityInput a <http://www.w3.org/ns/prov#Entity> ;
                    <http://www.w3.org/ns/prov#atLocation> ?entityInputLocation .
                        
                ?entityOutput a <http://www.w3.org/ns/prov#Entity> ; 
                    <http://www.w3.org/ns/prov#qualifiedGeneration>/<http://www.w3.org/ns/prov#activity> ?activity ;
                    <http://www.w3.org/ns/prov#atLocation> ?entityOutputLocation . 
                        
                FILTER ( ?entityInputLocation = '{input_notebook}' ) .
                    
        """
    else:
        query_where = """WHERE {
            {
                ?entityInput a <http://www.w3.org/ns/prov#Entity> ;
                    <http://www.w3.org/ns/prov#atLocation> ?entityInputLocation .
                    
                ?entityOutput a <http://www.w3.org/ns/prov#Entity> ; 
                    <http://www.w3.org/ns/prov#qualifiedGeneration>/<http://www.w3.org/ns/prov#activity> ?activity ;
                    <http://www.w3.org/ns/prov#atLocation> ?entityOutputLocation . 
                    
        """

    query_where += """
                OPTIONAL { ?actionParam <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition } .
            }
            {    
                ?activity a ?activityType ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#parameter> ?parameter_value ;
                    <http://www.w3.org/ns/prov#startedAtTime> ?activityTime ;
                    <http://www.w3.org/ns/prov#qualifiedAssociation>/<http://www.w3.org/ns/prov#hadPlan>/<https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                    <http://www.w3.org/ns/prov#qualifiedUsage>/<http://www.w3.org/ns/prov#entity> ?entityInput .
                    
            """
                    # <http://www.w3.org/ns/prov#qualifiedAssociation>/<http://www.w3.org/ns/prov#hadPlan> ?action ;
    if not no_oda_info:
        query_where += """
            OPTIONAL {
                {
                    ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                         <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                         a ?run_rdf_type ;
                         ^oa:hasBody/oa:hasTarget ?runId ;
                         ^oa:hasBody/oa:hasTarget ?activity .
                
                    ?aq_module <http://purl.org/dc/terms/title> ?aq_module_name ;
                        a ?aq_mod_rdf_type .

                    ?a_object <http://purl.org/dc/terms/title> ?a_object_name ;
                        a ?a_obj_rdf_type .

                    OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

                    ?run ?p ?o .

                    FILTER (!CONTAINS(str(?a_object), " ")) .
                }
                UNION
                {
                    ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                         <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region ;
                         a ?run_rdf_type ;
                         ^oa:hasBody/oa:hasTarget ?runId ;
                         ^oa:hasBody/oa:hasTarget ?activity .

                    ?aq_module a ?aq_mod_rdf_type ;
                        <http://purl.org/dc/terms/title> ?aq_module_name .

                    ?a_region a ?a_region_type ; 
                        <http://purl.org/dc/terms/title> ?a_region_name ;
                        <http://odahub.io/ontology#isUsingSkyCoordinates> ?a_sky_coordinates ;
                        <http://odahub.io/ontology#isUsingRadius> ?a_radius .

                    ?a_sky_coordinates a ?a_sky_coordinates_type ;
                        <http://purl.org/dc/terms/title> ?a_sky_coordinates_name .

                    ?a_radius a ?a_radius_type ;
                        <http://purl.org/dc/terms/title> ?a_radius_name .

                    OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

                    ?run ?p ?o .
                }
                UNION
                {
                    ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                         <http://odahub.io/ontology#isRequestingAstroImage> ?a_image ;
                         a ?run_rdf_type ;
                         ^oa:hasBody/oa:hasTarget ?runId ;
                         ^oa:hasBody/oa:hasTarget ?activity .

                    ?aq_module a ?aq_mod_rdf_type ;
                        <http://purl.org/dc/terms/title> ?aq_module_name .

                    ?a_image a ?a_image_type ;
                        <http://purl.org/dc/terms/title> ?a_image_name ;

                    OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingCoordinates> ?a_coordinates .
                         ?a_coordinates a ?a_coordinates_type ;
                             <http://purl.org/dc/terms/title> ?a_coordinates_name .
                    }}
                    OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingPosition> ?a_position .
                         ?a_position a ?a_position_type ;
                             <http://purl.org/dc/terms/title> ?a_position_name .
                    }}
                    OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingRadius> ?a_radius .
                        ?a_radius a ?a_radius_type ;
                            <http://purl.org/dc/terms/title> ?a_radius_name .
                    }}
                    OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingPixels> ?a_pixels .
                        ?a_pixels a ?a_pixels_type ;
                            <http://purl.org/dc/terms/title> ?a_pixels_name .
                    }}
                    OPTIONAL {{ ?a_image <http://odahub.io/ontology#isUsingImageBand> ?a_image_band .
                        ?a_image_band a ?a_image_band_type ;
                            <http://purl.org/dc/terms/title> ?a_image_band_name .
                    }}

                    OPTIONAL {{ ?run <http://purl.org/dc/terms/title> ?run_title . }}

                    ?run ?p ?o .
                }
            }
                """

    query_where += """
        }
    }
    """
    return query_where


def build_query_construct(no_oda_info=False):
    # add time activity information
    query_construct_action = """
                
            ?entityOutput a <https://swissdatasciencecenter.github.io/renku-ontology#CommandOutput> ;
                    <http://www.w3.org/ns/prov#atLocation> ?entityOutputLocation .
                
            ?entityInput a <http://www.w3.org/ns/prov#Entity> ;
                <http://www.w3.org/ns/prov#atLocation> ?entityInputLocation .
            
            ?activity a ?activityType ;
                <http://www.w3.org/ns/prov#startedAtTime> ?activityTime ;
                <https://swissdatasciencecenter.github.io/renku-ontology#hasInputs> ?entityInput ;
                <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                <https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs> ?entityOutput .
    """

    query_construct_oda_info = ""
    if not no_oda_info:
        query_construct_oda_info += """
                ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                    <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region ;
                    <http://odahub.io/ontology#isRequestingAstroImage> ?a_image ;
                    <http://purl.org/dc/terms/title> ?run_title ;
                    <http://odahub.io/ontology#isUsing> ?aq_module ;
                    oa:hasTarget ?activity ;
                    a ?run_rdf_type .
                
                ?aq_module <https://odahub.io/ontology#AQModule> ?aq_module_name ;
                    a ?aq_mod_rdf_type .

                ?a_object <https://odahub.io/ontology#AstroObject> ?a_object_name ;
                    a ?a_obj_rdf_type .

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

                ?a_pixels a ?a_pixels_type ;
                    <http://purl.org/dc/terms/title> ?a_pixels_name .

                ?a_image_band a ?a_image_band_type ;
                    <http://purl.org/dc/terms/title> ?a_image_band_name .

                ?a_coordinates a ?a_coordinates_type ;
                    <http://purl.org/dc/terms/title> ?a_coordinates_name .
                    
                ?a_sky_coordinates a ?a_sky_coordinates_type ;
                    <http://purl.org/dc/terms/title> ?a_sky_coordinates_name .
                    
                ?a_position a ?a_position_type ;
                    <http://purl.org/dc/terms/title> ?a_position_name .

                ?a_radius a ?a_radius_type ;
                    <http://purl.org/dc/terms/title> ?a_radius_name .
            """

    query_construct = f"""CONSTRUCT {{
                {query_construct_action}
                {query_construct_oda_info}
            }}"""

    return query_construct


def clean_graph(g):
    # remove not-needed predicates
    g.remove((None, rdflib.URIRef('http://odahub.io/ontology#isUsing'), None))
    g.remove((None, rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroRegion'), None))
    g.remove((None, rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroObject'), None))
    g.remove((None, rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroImage'), None))
    g.remove((None, rdflib.URIRef('http://purl.org/dc/terms/title'), None))
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/oa#hasTarget'), None))
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/prov#entity'), None))
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan'), None))
    g.remove((None, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#position'), None))
    g.remove((None, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasArguments'), None))
    g.remove((None, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasInputs'), None))
    # remove all the type triples
    g.remove((None, rdflib.RDF.type, None))


def analyze_types(g, type_label_values_dict):
    # analyze types
    types_list = g[:rdflib.RDF.type]
    for s, o in types_list:
        o_qname = g.compute_qname(o)
        s_label = label(s, g)
        type_label_values_dict[s_label] = o_qname[2]


def analyze_outputs(g, out_default_value_dict):
    # analyze outputs
    outputs_list = g[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs')]
    for s, o in outputs_list:
        s_label = label(s, g)
        if s_label not in out_default_value_dict:
            out_default_value_dict[s_label] = []
        output_obj_list = list(g[o:rdflib.URIRef('http://schema.org/defaultValue')])
        if len(output_obj_list) == 1:
            # get file extension
            file_extension = os.path.splitext(output_obj_list[0])[1][1:]

            if file_extension is not None:
                if file_extension in ['jpeg', 'jpg', 'png', 'gif', 'bmp']:
                    # removing old type, and assigning a new specific one
                    g.remove((o, rdflib.RDF.type, None))
                    g.add((o,
                           rdflib.RDF.type,
                           rdflib.URIRef("https://swissdatasciencecenter.github.io/renku-ontology#CommandOutputImage")))
                if file_extension in ['fits']:
                    # removing old type, and assigning a new specific one
                    g.remove((o, rdflib.RDF.type, None))
                    g.add((o,
                           rdflib.RDF.type,
                           rdflib.URIRef("https://swissdatasciencecenter.github.io/renku-ontology#CommandOutputFitsFile")))
                if file_extension == 'ipynb':
                    g.remove((o, rdflib.RDF.type, None))
                    g.add((o,
                           rdflib.RDF.type,
                           rdflib.URIRef(
                               "https://swissdatasciencecenter.github.io/renku-ontology#CommandOutputNotebook")))
                if file_extension == 'ecsv':
                    g.remove((o, rdflib.RDF.type, None))
                    g.add((o,
                           rdflib.RDF.type,
                           rdflib.URIRef(
                               "https://swissdatasciencecenter.github.io/renku-ontology#CommandOutputEcsvFile")))
            out_default_value_dict[s_label].append(output_obj_list[0])


def analyze_arguments(g, action_node_dict, args_default_value_dict):
    # analyze arguments (and join them all together)
    args_list = g[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasArguments')]
    for s, o in args_list:
        s_label = label(s, g)
        if s_label not in action_node_dict:
            action_node_dict[s_label] = s
        if s_label not in args_default_value_dict:
            args_default_value_dict[s_label] = []
        arg_obj_list = g[o:rdflib.URIRef('http://schema.org/defaultValue')]
        for arg_o in arg_obj_list:
            position_o = list(g[o:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#position')])
            if len(position_o) == 1:
                args_default_value_dict[s_label].append((arg_o.n3().strip('\"'), position_o[0].value))
                g.remove((o, rdflib.URIRef('http://schema.org/defaultValue'), arg_o))
    # infer isArgumentOf property for each action, this implies the creation of the new CommandParameter nodes
    # with the related defaultValue
    for action in args_default_value_dict.keys():
        arg_pos_list = args_default_value_dict[action].copy()
        # order according their position
        arg_pos_list.sort(key=lambda arg_tuple: arg_tuple[1])
        iter_arg_pos_list = iter(arg_pos_list)
        for x, y in zip(iter_arg_pos_list, iter_arg_pos_list):
            # create the node
            # TODO id needs to be properly assigned! now the name of the parameter is used
            node_args = rdflib.URIRef("https://github.com/plans/84d9b437-4a55-4573-9aa3-4669ff641f1b/parameters/"
                                      + x[0].replace(" ", "_") + "_" + y[0].replace(" ", "_"))
            # link it to the action node
            g.add((node_args,
                   rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#isArgumentOf'),
                   action_node_dict[action]))
            # value for the node args
            g.add((node_args,
                   rdflib.URIRef('http://schema.org/defaultValue'),
                   rdflib.Literal((x[0] + " " + y[0]).strip())))
            # type for the node args
            # TODO to discuss what the best approach to assign the type case is:
            # to create a node with a dedicated type inferred from the arguments
            # G.add((node_args,
            #        rdflib.RDF.type,
            #        rdflib.URIRef("https://swissdatasciencecenter.github.io/renku-ontology#" + x[0])))
            # or still create a new CommandParameter and use the defaultValue information
            g.add((node_args,
                   rdflib.RDF.type,
                   rdflib.URIRef("https://swissdatasciencecenter.github.io/renku-ontology#CommandParameter")))


def label(x, g):
    for labelProp in LABEL_PROPERTIES:
        l = g.value(x, labelProp)
        if l:
            return l
    try:
        return g.namespace_manager.compute_qname(x)[2]
    except:
        return x


def analyze_inputs(g):
    # analyze inputs
    for s, o in g[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasInputs')]:
        g.add((o, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#isInputOf'), s))


def extract_activity_start_time(g):
    # extract the info about the activity start time
    # get the activities and extract for each the startedTime into, and attach it to the related Action
    for activity_node, activity_start_time in g[:rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime')]:
        plan_list = g[activity_node:rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan')]
        for plan_node in plan_list:
            g.add((plan_node,
                   rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime'),
                   activity_start_time))
            g.remove((activity_node,
                      rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime'),
                      activity_start_time))


def process_oda_info(g):
    run_target_list = g[:rdflib.URIRef('http://www.w3.org/ns/oa#hasTarget')]
    for run_node, activity_node in run_target_list:
        # # or plan_node list
        # for action_node in g[activity_node:rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan')]:
        # we inferred a connection from the run to an action
        # and we can now infer the request of a certain astroObject and the usage of a certain module
        used_module_list = list(g[run_node:rdflib.URIRef('http://odahub.io/ontology#isUsing')])
        # one module in use per annotation and one requested AstroObject/AstroRegion
        module_node = used_module_list[0]
        # query_object
        process_query_object_info(g, run_node=run_node, module_node=module_node, activity_node=activity_node)
        # query_region
        process_query_region_info(g, run_node=run_node, module_node=module_node, activity_node=activity_node)
        # get_images
        process_get_images_info(g, run_node=run_node, module_node=module_node, activity_node=activity_node)


def process_query_object_info(g, run_node=None, module_node=None, activity_node=None):
    requested_astroObject_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroObject')])
    if len(requested_astroObject_list) > 0:
        # if run_node is of the type query_object
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               activity_node))
        # for astroObject_node in requested_astroObject_list:
        astroObject_node = requested_astroObject_list[0]
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#requestsAstroObject'),
               astroObject_node))


def process_query_region_info(g, run_node=None, module_node=None, activity_node=None):
    requested_astroRegion_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroRegion')])
    if len(requested_astroRegion_list) > 0:
        # if run_node is of the type query_region
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               activity_node))
        # for astroObject_node in requested_astroObject_list:
        astroRegion_node = requested_astroRegion_list[0]
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#requestsAstroRegion'),
               astroRegion_node))
        # sky coordinates info (if found, perhaps some for old query_region none was stored)
        sky_coordinates_list = list(
            g[astroRegion_node:rdflib.URIRef('http://odahub.io/ontology#isUsingSkyCoordinates')])
        if len(sky_coordinates_list) == 1:
            sky_coordinates_node = sky_coordinates_list[0]
            sky_coordinates_node_title = list(
                g[sky_coordinates_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(sky_coordinates_node_title) == 1:
                process_skycoord_obj(g, sky_coordinates_node, sky_coordinates_node_title)
        # radius info (if found, perhaps some for old query_region none was stored)
        radius_list = list(
            g[astroRegion_node:rdflib.URIRef('http://odahub.io/ontology#isUsingRadius')])
        if len(radius_list) == 1:
            radius_node = radius_list[0]
            radius_node_title = list(
                g[radius_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(radius_node_title) == 1:
                # define an astropy Angle object
                process_angle_obj(g, radius_node, radius_node_title[0].value)


def process_get_images_info(g, run_node=None, module_node=None, activity_node=None):
    requested_astroImage_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroImage')])
    if len(requested_astroImage_list) > 0:
        # if run_node is of the type get_images
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               activity_node))
        # for astroObject_node in requested_astroObject_list:
        astroImage_node = requested_astroImage_list[0]
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#requestsAstroImage'),
               astroImage_node))
        # position info (if found, they could be parsed top SkyCoordinates like in query_region)
        coordinates_list = list(
            g[astroImage_node:rdflib.URIRef('http://odahub.io/ontology#isUsingCoordinates')])
        if len(coordinates_list) == 1:
            coordinates_node = coordinates_list[0]
            coordinates_node_title = list(
                g[coordinates_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(coordinates_node_title) == 1:
                coordinates = coordinates_node_title[0].value.split(" ")
                if len(coordinates) == 1:
                    coordinates_obj_default_value = ",".join(coordinates)
                    g.add((coordinates_node, rdflib.URIRef('http://schema.org/defaultValue'),
                           rdflib.Literal(coordinates_obj_default_value)))
        # position info (if found, they could be parsed top SkyCoordinates like in query_region)
        position_list = list(
            g[astroImage_node:rdflib.URIRef('http://odahub.io/ontology#isUsingPosition')])
        if len(position_list) == 1:
            position_node = position_list[0]
            position_node_title = list(
                g[position_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(position_node_title) == 1:
                process_skycoord_obj(g, position_node, position_node_title)
        # radius info (if found, perhaps some for old query_region none was stored)
        radius_list = list(
            g[astroImage_node:rdflib.URIRef('http://odahub.io/ontology#isUsingRadius')])
        if len(radius_list) == 1:
            radius_node = radius_list[0]
            radius_node_title = list(
                g[radius_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(radius_node_title) == 1:
                # define an astropy Angle object
                process_angle_obj(g, radius_node, radius_node_title[0].value)
        # pixels info (if found, perhaps some for old query_region none was stored)
        pixels_list = list(
            g[astroImage_node:rdflib.URIRef('http://odahub.io/ontology#isUsingPixels')])
        if len(pixels_list) == 1:
            pixels_node = pixels_list[0]
            pixels_node_node_title = list(
                g[pixels_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(pixels_node_node_title) == 1:
                # define an astropy SkyCoord object
                pixels = pixels_node_node_title[0].value.split(" ")
                pixels_obj_default_value = ",".join(pixels)
                g.add((pixels_node, rdflib.URIRef('http://schema.org/defaultValue'),
                       rdflib.Literal(pixels_obj_default_value)))
        # image band info (if found, perhaps some for old query_region none was stored)
        image_band_list = list(
            g[astroImage_node:rdflib.URIRef('http://odahub.io/ontology#isUsingImageBand')])
        if len(image_band_list) == 1:
            image_band_node = image_band_list[0]
            image_band_node_title = list(
                g[image_band_node:rdflib.URIRef('http://purl.org/dc/terms/title')])
            if len(image_band_node_title) == 1:
                # define an astropy SkyCoord object
                image_band_value = image_band_node_title[0].value
                g.add((image_band_node, rdflib.URIRef('http://schema.org/defaultValue'),
                       rdflib.Literal(image_band_value)))


def process_angle_obj(g, angle_node, angle_value):
    # define an astropy Angle object
    radius_obj = Angle(angle_value)
    radius_obj_default_value = str(radius_obj.arcmin) + " unit=arcmin"
    g.add((angle_node, rdflib.URIRef('http://schema.org/defaultValue'),
           rdflib.Literal(radius_obj_default_value)))


def process_skycoord_obj(g, coordinate_node, coordinate_value):
    # define an astropy SkyCoord object
    # TODO optimize and define a standard way to detect and parse a SkyCoord object
    coords_comma = coordinate_value[0].value.split(",")
    coords_space = coordinate_value[0].value.split(" ")
    sky_coord_obj_default_value = None
    coords = None
    if len(coords_space) == 2:
        coords = coords_space
    elif len(coords_comma) == 2:
        coords = coords_comma
    else:
        sky_coord_obj_default_value = ",".join(coordinate_value[0].value)
    if coords is not None and len(coords) == 2:
        sky_coord_obj = SkyCoord(coords[0], coords[1], unit='degree')
        sky_coord_obj_default_value = 'RA=' + str(sky_coord_obj.ra.deg) + ' deg ' + \
                                      ' Dec=' + str(sky_coord_obj.dec.deg) + ' deg'
    if sky_coord_obj_default_value is not None:
        g.add((coordinate_node, rdflib.URIRef('http://schema.org/defaultValue'),
               rdflib.Literal(sky_coord_obj_default_value)))
