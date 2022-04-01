import os
import typing
import pydotplus
import rdflib
import bs4

from rdflib.tools.rdf2dot import LABEL_PROPERTIES
from lxml import etree
from dateutil import parser
from astropy.coordinates import SkyCoord, Angle


def set_graph_options(graph):
    graph.set_options(
        """{
            "physics": {
                "hierarchicalRepulsion": {
                    "nodeDistance": 175,
                    "damping": 0.15
                },
                "minVelocity": 0.75,
                "solver": "hierarchicalRepulsion"
            },
            "configure": {
                "filter": ""
            },
            "layout": {
                "hierarchical": {
                    "enabled": true,
                    "levelSeparation": -150,
                    "sortMethod": "directed"
                }
            },
            "nodes": {
                "scaling": {
                  "min": 10,
                  "max": 100,
                  "label": {
                    "enabled": true
                  }
                },
                "labelHighlightBold": true
            },
            "edges": {
                "arrows": {
                  "to": {
                    "enabled": true,
                    "scaleFactor": 0.45
                    }
                },
                "arrowStrikethrough": true,
                "color": {
                    "inherit": true
                },
                "physics": false,
                "smooth": false
            }
        }"""
    )


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


def build_query_where(input_notebook: str = None):
    if input_notebook is not None:
        query_where = f"""WHERE {{
            {{
            ?action a <http://schema.org/Action> ; 
                <https://swissdatasciencecenter.github.io/renku-ontology#hasInputs> ?actionParamInput ;
                <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                ?has ?actionParam .

            ?actionParamInput a ?actionParamInputType ;
                <http://schema.org/defaultValue> '{input_notebook}' .

            FILTER ( ?actionParamInputType = <https://swissdatasciencecenter.github.io/renku-ontology#CommandInput>) .

            FILTER (?has IN (<https://swissdatasciencecenter.github.io/renku-ontology#hasArguments>, 
                <https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs>
                ))

            ?actionParam a ?actionParamType ;
                <http://schema.org/defaultValue> ?actionParamValue .

            FILTER ( ?actionParamType IN (<https://swissdatasciencecenter.github.io/renku-ontology#CommandOutput>,
                                        <https://swissdatasciencecenter.github.io/renku-ontology#CommandParameter>)
                                        ) .
        """
    else:
        query_where = """WHERE {
            {
                ?action a <http://schema.org/Action> ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                    ?has ?actionParam .

                FILTER (?has IN (<https://swissdatasciencecenter.github.io/renku-ontology#hasArguments>,
                    <https://swissdatasciencecenter.github.io/renku-ontology#hasOutputs>,
                    <https://swissdatasciencecenter.github.io/renku-ontology#hasInputs>
                    ))

                ?actionParam a ?actionParamType ;
                    <http://schema.org/defaultValue> ?actionParamValue .

                FILTER ( ?actionParamType IN (<https://swissdatasciencecenter.github.io/renku-ontology#CommandOutput>,
                                        <https://swissdatasciencecenter.github.io/renku-ontology#CommandParameter>,
                                        <https://swissdatasciencecenter.github.io/renku-ontology#CommandInput>)
                                        ) .
        """

    query_where = query_where + """
                OPTIONAL { ?actionParam <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition } .
            }

            {
                ?activity a ?activityType ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#parameter> ?parameter_value ;
                    <http://www.w3.org/ns/prov#startedAtTime> ?activityTime ;
                    <http://www.w3.org/ns/prov#qualifiedAssociation> ?activity_qualified_association .

                ?activity_qualified_association <http://www.w3.org/ns/prov#hadPlan> ?action .

                {
                    ?run <http://odahub.io/ontology#isUsing> ?aq_module ;
                         <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                         a ?run_rdf_type ;
                         ^oa:hasBody/oa:hasTarget ?runId ;
                         ^oa:hasBody/oa:hasTarget ?activityRun .
                
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
                         ^oa:hasBody/oa:hasTarget ?activityRun .

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
                         ^oa:hasBody/oa:hasTarget ?activityRun .

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
        }
        """
    return query_where


def build_query_construct_base_graph(no_oda_info=False):
    query_construct_action = """
            ?action a <http://schema.org/Action> ;
                <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand .
        
            ?activity a ?activityType ;
                <http://www.w3.org/ns/prov#startedAtTime> ?activityTime ;
                <http://www.w3.org/ns/prov#qualifiedAssociation> ?activity_qualified_association .

            ?activity_qualified_association <http://www.w3.org/ns/prov#hadPlan> ?action .
    """

    query_construct = f"""CONSTRUCT {{
                {query_construct_action}
            }}"""

    return query_construct


def build_query_per_node(node):
    pass


def build_query_construct(input_notebook: str = None, no_oda_info=False):
    if input_notebook is not None:
        query_construct_action = f"""
                ?action a <http://schema.org/Action> ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#hasInputs> ?actionParamInput ;
                    ?has ?actionParam .

                ?actionParamInput a ?actionParamInputType ;
                    <http://schema.org/defaultValue> '{input_notebook}' .

                ?actionParam a ?actionParamType ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition ;
                    <http://schema.org/defaultValue> ?actionParamValue .
        """
    else:
        query_construct_action = """
                ?action a <http://schema.org/Action> ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#command> ?actionCommand ;
                    ?has ?actionParam .

                ?actionParam a ?actionParamType ;
                    <https://swissdatasciencecenter.github.io/renku-ontology#position> ?actionPosition ;
                    <http://schema.org/defaultValue> ?actionParamValue .
        """
    # add time activity information
    query_construct_action += """
            ?activity a ?activityType ;
                <http://www.w3.org/ns/prov#startedAtTime> ?activityTime ;
                <http://www.w3.org/ns/prov#qualifiedAssociation> ?activity_qualified_association .

            ?activity_qualified_association <http://www.w3.org/ns/prov#hadPlan> ?action .
    """

    query_construct_oda_info = ""
    if not no_oda_info:
        query_construct_oda_info += """
                ?run <http://odahub.io/ontology#isRequestingAstroObject> ?a_object ;
                    <http://odahub.io/ontology#isRequestingAstroRegion> ?a_region ;
                    <http://odahub.io/ontology#isRequestingAstroImage> ?a_image ;
                    <http://purl.org/dc/terms/title> ?run_title ;
                    <http://odahub.io/ontology#isUsing> ?aq_module ;
                    oa:hasTarget ?activityRun ;
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
    # remove not-needed triples
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan'), None))
    g.remove((None, rdflib.URIRef('http://purl.org/dc/terms/title'), None))
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/prov#qualifiedAssociation'), None))
    g.remove((None, rdflib.URIRef('http://www.w3.org/ns/oa#hasTarget'), None))
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


def analyze_inputs(g, in_default_value_dict):
    # analyze inputs
    inputs_list = g[:rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#hasInputs')]
    for s, o in inputs_list:
        s_label = label(s, g)
        if s_label not in in_default_value_dict:
            in_default_value_dict[s_label] = []
        input_obj_list = g[o]
        for input_p, input_o in input_obj_list:
            if input_p.n3() == "<http://schema.org/defaultValue>":
                in_default_value_dict[s_label].append(input_o.n3().strip('\"'))
        # infer isInputOf property
        g.add((o, rdflib.URIRef('https://swissdatasciencecenter.github.io/renku-ontology#isInputOf'), s))


def extract_activity_start_time(g):
    # extract the info about the activity start time
    # get the activities and extract for each the startedTime into, and attach it to the related Action
    start_time_activity_list = g[:rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime')]

    for activity_node, activity_start_time in start_time_activity_list:
        # get the association and then the action
        qualified_association_list = g[activity_node:rdflib.URIRef(
            'http://www.w3.org/ns/prov#qualifiedAssociation')]
        for association_node in qualified_association_list:
            plan_list = g[association_node:rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan')]
            for plan_node in plan_list:
                g.add(
                    (plan_node, rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime'), activity_start_time))
                g.remove((activity_node, rdflib.URIRef('http://www.w3.org/ns/prov#startedAtTime'),
                          activity_start_time))


def process_oda_info(g):
    # find a way to the action form the Run by extracting activity qualified association
    run_target_list = g[:rdflib.URIRef('http://www.w3.org/ns/oa#hasTarget')]
    for run_node, activity_node in run_target_list:
        # run_node is the run, act_node is the activity
        qualified_association_list = g[activity_node:rdflib.URIRef('http://www.w3.org/ns/prov#qualifiedAssociation')]
        for association_node in qualified_association_list:
            action_list = g[association_node:rdflib.URIRef('http://www.w3.org/ns/prov#hadPlan')]
            # or plan_node list
            for action_node in action_list:
                # we inferred a connection from the run to an action
                # and we can now infer the request of a certain astroObject and the usage of a certain module
                used_module_list = list(g[run_node:rdflib.URIRef('http://odahub.io/ontology#isUsing')])
                # one module in use per annotation and one requested AstroObject/AstroRegion
                module_node = used_module_list[0]
                # query_object
                process_query_object_info(g, run_node=run_node, module_node=module_node, action_node=action_node)
                # query_region
                process_query_region_info(g, run_node=run_node, module_node=module_node, action_node=action_node)
                # get_images
                process_get_images_info(g, run_node=run_node, module_node=module_node, action_node=action_node)

                # some clean-up
                g.remove((run_node,
                          rdflib.URIRef('http://odahub.io/ontology#isUsing'),
                          None))
                g.remove((run_node,
                          rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroRegion'),
                          None))
                g.remove((run_node,
                          rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroObject'),
                          None))
                g.remove((run_node,
                          rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroImage'),
                          None))


def process_query_object_info(g, run_node=None, module_node=None, action_node=None):
    requested_astroObject_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroObject')])
    if len(requested_astroObject_list) > 0:
        # if run_node is of the type query_object
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               action_node))
        # for astroObject_node in requested_astroObject_list:
        astroObject_node = requested_astroObject_list[0]
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#requestsAstroObject'),
               astroObject_node))


def process_query_region_info(g, run_node=None, module_node=None, action_node=None):
    requested_astroRegion_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroRegion')])
    if len(requested_astroRegion_list) > 0:
        # if run_node is of the type query_region
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               action_node))
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


def process_get_images_info(g, run_node=None, module_node=None, action_node=None):
    requested_astroImage_list = list(
        g[run_node:rdflib.URIRef('http://odahub.io/ontology#isRequestingAstroImage')])
    if len(requested_astroImage_list) > 0:
        # if run_node is of the type get_images
        # for module_node in used_module_list:
        g.add((module_node, rdflib.URIRef('http://odahub.io/ontology#isUsedDuring'),
               action_node))
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


def add_js_click_functionality(net, output_path, hidden_nodes_dic, hidden_edges_dic):
    f_click = '''
    var toggle = false;
    network.on("click", function(e) {
        selected_node = nodes.get(e.nodes[0]);
        if (selected_node.hasOwnProperty('type') && (selected_node.type == "Action" || selected_node.type.startsWith("Astrophysical"))) {
        '''
    for hidden_edge in hidden_edges_dic:
        hidden_node_id = None
        if hidden_edge['dest_node'] in hidden_nodes_dic:
            hidden_node_id = hidden_edge['dest_node']
        elif hidden_edge['source_node'] in hidden_nodes_dic:
            hidden_node_id = hidden_edge['source_node']
        if hidden_node_id is not None:
            node_label = hidden_nodes_dic[hidden_node_id]['label'].replace("\n", '\\n')
            node_title = hidden_nodes_dic[hidden_node_id]['title'].replace("\n", '\\n')
            f_click += f'''
                if(selected_node.id == "{hidden_edge['source_node']}" || selected_node.id == "{hidden_edge['dest_node']}") {{
                    if(edges.get("{hidden_edge['id']}") == null) {{
                        nodes.add([
                            {{id: "{hidden_node_id}",
                            label: "{node_label}",
                            title: "{node_title}",
                            color: "{hidden_nodes_dic[hidden_node_id]['color']}",
                            shape: "{hidden_nodes_dic[hidden_node_id]['shape']}",
                            type: "{hidden_nodes_dic[hidden_node_id]['type']}",
                            font: {hidden_nodes_dic[hidden_node_id]['font']},
                            level: "{hidden_nodes_dic[hidden_node_id]['level']}"}}
                        ]);
                        edges.add([
                            {{id: "{hidden_edge['id']}", 
                            from: "{hidden_edge['source_node']}", 
                            to: "{hidden_edge['dest_node']}", 
                            title:"{hidden_edge['title']}", 
                            hidden:false }}
                        ]);
                    }}
                    else {{
                        nodes.remove([
                            {{id: "{hidden_node_id}"}}
                        ])
                        edges.remove([
                            {{id: "{hidden_edge['id']}"}},
                        ]);
                    }}
                }}
        '''

    f_click += '''
        }
        // network.fit();
        // network.redraw();
    });

    var container_configure = document.getElementsByClassName("vis-configuration-wrapper");
    if(container_configure) {
        container_configure = container_configure[0];
        container_configure.style = {};
        container_configure.style.height="300px";
        container_configure.style.overflow="scroll";
    }
    return network;
    '''
    net.html = net.html.replace('return network;', f_click)

    with open(output_path, "w+") as out:
        out.write(net.html)


def update_vis_library_version(html_fn):
    # let's patch the template
    # load the file
    with open(html_fn) as template:
        html_code = template.read()
        soup = bs4.BeautifulSoup(html_code, "html.parser")

    soup.head.link.decompose()
    soup.head.script.decompose()

    new_script = soup.new_tag("script", type="application/javascript",
                              src="https://unpkg.com/vis-network/standalone/umd/vis-network.js")
    soup.head.append(new_script)

    # save the file again
    with open(html_fn, "w") as outf:
        outf.write(str(soup))
