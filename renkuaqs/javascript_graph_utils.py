import re
import subprocess
import os
import bs4
import shutil

from lxml import etree
from dateutil import parser


def set_graph_options(net, output_path):
    options_str = (
        """

        var options = {
            autoResize: true,
            nodes: {
                scaling: {
                    min: 10,
                    max: 30
                },
                font: {
                    size: 14,
                    face: "Tahoma",
                },
            },
            edges: {
                smooth: false,
                arrows: {
                  to: {
                    enabled: true,
                    scaleFactor: 1.2
                    }
                },
                width: 4

            },
            layout: {
                hierarchical: {
                    enabled: false
                }
            },
            interaction: {

            },
        };

        """
    )
    net_html_match = re.search(r'var options = {.*};', net.html, flags=re.DOTALL)
    if net_html_match is not None:
        net.html = net.html.replace(net_html_match.group(0), options_str)

    with open(output_path, "w+") as out:
        out.write(net.html)


def set_html_content(net, output_path,
                     graph_config_names_list=None,
                     nodes_graph_config_obj_dict=None,
                     edges_graph_config_obj_dict=None,
                     graph_reduction_config_obj_dict=None,
                     graph_nodes_subset_config_obj_dict=None):
    # print(json.dumps(nodes_graph_config_obj_dict, indent=4, sort_keys=True))
    # print(json.dumps(edges_graph_config_obj_dict, indent=4, sort_keys=True))

    html_code = '''
        <div style="margin: 5px 0px 15px 5px">
            <button type="button" onclick="reset_graph()">Reset graph!</button>
            <button type="button" onclick="fit_graph()">Fit graph!</button>
            <button type="button" onclick="stop_animation()">Stop animation!</button>
        </div>
        <div style="display:flex;">
            <div style="background-color: #F7F7F7; border-left: 1px double; border-right: 1px double; padding: 5px; margin: 5px 0px 10px 5px">
                <h3 style="margin: 15px 0px 10px 5px;">Change graph layout</h3>

                <div style="margin: 5px">
                    <label><input type="radio" id="repulsion_layout" name="graph_layout" value="repulsion" onchange="toggle_layout(this)" checked>
                    Random</label>
                </div>
                <div style="margin: 5px">
                    <label><input type="radio" id="hierarchical_layout" name="graph_layout" value="hierarchicalRepulsion" onchange="toggle_layout(this)" unchecked>
                    Hierarchical</label>
                </div>
            </div>
        '''

    if graph_nodes_subset_config_obj_dict is not None:
        html_code += (
            '<div style="background-color: #F7F7F7; border-right: 1px double; padding: 5px; margin: 5px 0px 10px 5px">'
            '<h3 style="margin: 15px 0px 10px 5px;">Enable/disable selections</h3>')
        for nodes_subset_obj in graph_nodes_subset_config_obj_dict:
            prefixes_values = graph_nodes_subset_config_obj_dict[nodes_subset_obj]['prefixes']
            html_code += (f'''
                <div style="margin: 5px">
                    <label><input type="checkbox" id="{nodes_subset_obj}_filter" 
                        value="{prefixes_values}" 
                        onchange="enable_filter(this)" checked>
                        oda astroquery-related nodes</label>
                    </div>
                </div>
            ''')

    if graph_reduction_config_obj_dict is not None:
        html_code += (
            '<div style="background-color: #F7F7F7; border-right: 1px double; padding: 5px; margin: 5px 0px 10px 5px">'
            '<h3 style="margin: 15px 0px 10px 5px;">Apply reductions</h3>')
        for reduction_obj_id in graph_reduction_config_obj_dict:
            html_code += (f'''
                <div style="margin: 5px">
                    <label><input type="checkbox" id="reduction_config_{reduction_obj_id}" onchange="apply_reduction_change(this)"
                    value="{reduction_obj_id}" unchecked>{graph_reduction_config_obj_dict[reduction_obj_id]["name"]}</label>
                </div>
            ''')
        html_code += '</div>'

    checkboxes_config_added = []
    if graph_config_names_list is not None:
        html_code += (
            '<div style="border-right: 1px double; padding: 5px; background-color: #F7F7F7; margin: 5px 0px 15px 5px">'
            '<h3 style="margin: 15px 0px 10px 5px;">Enable/disable graphical configurations</h3>')
        for config_node_type in nodes_graph_config_obj_dict:
            if 'config_file' in nodes_graph_config_obj_dict[config_node_type]:
                graph_config_name = nodes_graph_config_obj_dict[config_node_type]['config_file']
                if graph_config_name not in checkboxes_config_added:
                    # for graph_config_name in graph_config_names_list:
                    html_code += f'''
                        <div style="margin: 5px">
                            <label><input type="checkbox" id="config_{graph_config_name}" value="{graph_config_name}" onchange="toggle_graph_config(this)" checked>
                            {graph_config_name}</label>
                        </div>
                    '''
                    checkboxes_config_added.append(graph_config_name)

        for config_edge_type in edges_graph_config_obj_dict:
            if 'config_file' in edges_graph_config_obj_dict[config_edge_type]:
                graph_config_name = edges_graph_config_obj_dict[config_edge_type]['config_file']
                if graph_config_name not in checkboxes_config_added:
                    # for graph_config_name in graph_config_names_list:
                    html_code += f'''
                        <div style="margin: 5px">
                            <label><input type="checkbox" id="config_{graph_config_name}" value="{graph_config_name}" onchange="toggle_graph_config(this)" checked>
                            {graph_config_name}</label>
                        </div>
                    '''
                    checkboxes_config_added.append(graph_config_name)

    html_code += '''
                </div>
            </div>
            <div style="display: flex;">
                <div style="margin:10px;">
                    <div style="margin: 0px 0px 5px 5px; font-weight: bold; ">Legend</div>
                    <ul id="legend_container" style="overflow: scroll; padding-right:15px; overflow-x:hidden; background-color: #F7F7F7"></ul>
                </div>
                <div id="mynetwork"></div>
            </div>
    '''

    net.html = net.html.replace('<html>', '<!DOCTYPE html>')
    net_h1_html_match = re.search(r'<center>.*<h1></h1>.*</center>', net.html, flags=re.DOTALL)
    if net_h1_html_match is not None:
        net.html = net.html.replace(net_h1_html_match.group(0), '')
    net.html = net.html.replace('<body>', ('<body>'
                                           '<h1>ODA Graph Export Quick-Look</h1>'))
    net.html = net.html.replace('<div id = "mynetwork"></div>', html_code)
    with open(output_path, "w+") as out:
        out.write(net.html)


def add_js_click_functionality(net, output_path, graph_ttl_stream=None,
                               nodes_graph_config_obj_str=None,
                               edges_graph_config_obj_str=None,
                               graph_reductions_obj_str=None,
                               graph_nodes_subset_config_obj_str=None):
    f_graph_vars = f'''

        var graph_reductions_obj = JSON.parse('{graph_reductions_obj_str}');
        var nodes_graph_config_obj = JSON.parse('{nodes_graph_config_obj_str}');
        var edges_graph_config_obj = JSON.parse('{edges_graph_config_obj_str}');
        var subset_nodes_config_obj = JSON.parse('{graph_nodes_subset_config_obj_str}');

    '''

    f_draw_graph = f'''
        parsed_graph = parser.parse(`{graph_ttl_stream}`,
            function (error, triple, prefixes) {{
                // Always log errors
                if (error) {{
                    console.error(error);
                }}
                if (triple) {{
                    store.addQuad(triple.subject, triple.predicate, triple.object);
                }} else {{
                    prefixes_graph = prefixes;
                    (async() => {{
                        const bindingsStreamCall = await myEngine.queryQuads(query_initial_graph,
                            {{
                                sources: [ store ] 
                            }}
                        ); 
                        bindingsStreamCall.on('data', (binding) => {{
                            process_binding(binding);
                        }});
                        bindingsStreamCall.on('end', () => {{
                            let checked_radiobox = document.querySelector('input[name="graph_layout"]:checked');
                            toggle_layout(checked_radiobox);
                        }});
                        bindingsStreamCall.on('error', (error) => {{ 
                            console.error(error);
                        }});
                    }})();
                }}

            }}
        );

        network.on("stabilized", function (e) {{
            stop_animation();
        }});

        network.on("dragStart", function (e) {{
            stop_animation();
            if(e.nodes[0])
                fix_release_nodes(false, e.nodes[0]);
        }});

        network.on("click", function(e) {{
            if(e.nodes[0]) {{
                if(nodes.get(e.nodes[0])['clickable']) {{
                    let clicked_node = nodes.get(e.nodes[0]);
                    console.log(clicked_node);
                    if (!('expanded' in clicked_node) || !clicked_node['expanded']) {{
                        nodes.update({{
                            id: clicked_node.id,
                            expanded: true
                        }});
                        // fix all the current nodes
                        fix_release_nodes();
                        let checkbox_reduction;
                        apply_invisibility_new_nodes = false;
                        if (clicked_node.hasOwnProperty("type_name")) {{
                            checkbox_reduction = document.getElementById('reduction_config_' + clicked_node.type_name);
                        }}
                        apply_invisibility_new_nodes = true;
                        (async() => {{
                            const bindingsStreamCall = await myEngine.queryQuads(
                                format_query_clicked_node(clicked_node.id),
                                {{
                                    sources: [ store ]
                                }}
                            );
                            bindingsStreamCall.on('data', (binding) => {{
                                process_binding(binding, clicked_node, apply_invisibility_new_nodes);
                            }});
                            bindingsStreamCall.on('end', () => {{
                                // enable/disable subsets of nodes selection from the graph
                                for (let prefix_idx in prefixes_graph) {{
                                    let checkbox_config = document.getElementById(prefix_idx + '_filter');
                                    if (checkbox_config !== null && !checkbox_config.checked) {{
                                        let values_input = checkbox_config.value.split(",");
                                        for (let value_input_idx in values_input) {{
                                            let nodes_to_filter = nodes.get({{
                                                filter: function (item) {{
                                                    return (item.prefix === prefixes_graph[values_input[value_input_idx].trim()]);
                                                }}
                                            }});
                                            // nodes.remove(nodes_to_filter);
                                            nodes_to_filter.forEach(node => {{
                                                nodes.update({{id: node.id, hidden: true, filtered_out: true}});
                                            }});
                                        }}
                                    }}
                                }}
                                //
                                // apply layout
                                let checked_radiobox = document.querySelector('input[name="graph_layout"]:checked');
                                toggle_layout(checked_radiobox);
                                //
                                // apply reductions
                                if (checkbox_reduction !== undefined &&
                                    checkbox_reduction !== null &&
                                    clicked_node.type_name in graph_reductions_obj) {{
                                    let reduction_subset =  graph_reductions_obj[clicked_node.type_name];
                                    let predicates_to_absorb_list = reduction_subset["predicates_to_absorb"].split(",");
                                    let origin_node_list = nodes.get({{
                                        filter: function (item) {{
                                            return (item.id === clicked_node.id);
                                        }}
                                    }});
                                    if(checkbox_reduction.checked) {{
                                        absorb_nodes(origin_node_list, predicates_to_absorb_list);
                                    }}
                                }}
                                //
                                // show any hidden nodes
                                const hidden_nodes_ids = nodes.get({{
                                    filter: function (item) {{
                                        return (item.hasOwnProperty("hidden") && item.hidden === true && item.filtered_out === false);
                                    }}
                                }});
                                hidden_nodes_ids.forEach(node => {{
                                    nodes.update({{id: node.id, hidden: false}});
                                }});
                                // remove edges that are not visible because one of the connected nodes has been removed
                                remove_unused_edges();
                            }});
                            bindingsStreamCall.on('error', (error) => {{ 
                                console.error(error);
                            }});
                        }})();
                    }}
                    else {{
                        let connected_to_nodes = network.getConnectedNodes(clicked_node.id);
                        let nodes_to_remove = [];
                        let edges_to_remove = [];
                        if (connected_to_nodes.length > 0) {{
                            for (let i in connected_to_nodes) {{
                                let connected_to_node = connected_to_nodes[i];
                                connected_to_connected_to_node = network.getConnectedNodes(connected_to_node);
                                if (connected_to_connected_to_node.length == 1) {{
                                    nodes_to_remove.push(connected_to_node);
                                    edges_to_remove.push(...network.getConnectedEdges(connected_to_node));
                                }}
                            }}
                        }}

                        let original_label = clicked_node.hasOwnProperty('original_label') ? clicked_node.original_label : clicked_node.label;
                        nodes.update({{
                            id: clicked_node.id,
                            label: original_label,
                            child_nodes_list_content: [],
                            expanded: false
                        }});

                        edges.remove(edges_to_remove);
                        nodes.remove(nodes_to_remove);
                    }}
                }}
            }}
        }});

        var container_configure = document.getElementsByClassName("vis-configuration-wrapper");
        if(container_configure && container_configure.length > 0) {{
            container_configure = container_configure[0];
            container_configure.style = {{}};
            container_configure.style.height="300px";
            container_configure.style.overflow="scroll";
        }}

        // legend
        reset_legend();

        return network;
    }}
    '''
    net_html_match = re.search(r'return network;.*}', net.html, flags=re.DOTALL)
    if net_html_match is not None:
        net.html = net.html.replace(net_html_match.group(0), f_draw_graph)

    net.html = net.html.replace('// initialize global variables.', f_graph_vars)

    with open(output_path, "w+") as out:
        out.write(net.html)


def set_html_head(html_fn):
    # let's patch the template
    # load the file
    with open(html_fn) as template:
        html_code = template.read()
        soup = bs4.BeautifulSoup(html_code, "html.parser")

    soup.head.link.decompose()
    soup.head.script.decompose()

    css_tag = soup.head.find('style', type="text/css")
    css_tag.string += ('h1 {\n'
                       '  font-family: \"Source Sans Pro\", sans-serif;\n'
                       '  font-weight: 700;\n'
                       '  color: rgb(49, 51, 63);\n'
                       '  line-height: 1.2;\n'
                       '}')

    new_script_updated_vis_library = soup.new_tag("script", type="application/javascript",
                                                  src="https://unpkg.com/vis-network/standalone/umd/vis-network.js")
    soup.head.append(new_script_updated_vis_library)

    new_script_rdflib_library = soup.new_tag("script", type="application/javascript",
                                             src="https://unpkg.com/n3/browser/n3.min.js")
    soup.head.append(new_script_rdflib_library)

    new_script_query_sparql_library = soup.new_tag("script", type="application/javascript",
                                                   src="https://rdf.js.org/comunica-browser/versions/latest"
                                                       "/engines/query-sparql-rdfjs/comunica-browser.js")
    soup.head.append(new_script_query_sparql_library)

    new_script_jquery_library = soup.new_tag("script", type="application/javascript",
                                             src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js")
    soup.head.append(new_script_jquery_library)

    # TODO git clone js library from git, better to have it in a proper location
    repo_name = "renku-aqs-graph-library"
    repo_dir = repo_name

    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    subprocess.check_call(
        ["git", "clone", f"git@github.com:burnout87/{repo_name}.git", "renku-aqs-graph-library"]
    )
    graph_helper_library = soup.new_tag("script", type="application/javascript",
                                        src="renku-aqs-graph-library/graph_helper.js")
    soup.head.append(graph_helper_library)

    title_tag = soup.new_tag("title")
    title_tag.string = "Graph visualization"
    soup.head.append(title_tag)

    # save the file again
    with open(html_fn, "w") as outf:
        outf.write(str(soup))
