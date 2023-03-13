import bs4
import os
from git import Repo


def gitignore_file(file_name):
    if os.path.exists('.gitignore'):
        with open('.gitignore') as gitignore_file_lines:
            lines = gitignore_file_lines.readlines()
        if file_name + "\n" not in lines:
            lines.append(file_name + "\n")
            with open(".gitignore", "w") as gitignore_file_write:
                gitignore_file_write.writelines(lines)
            commit_msg = f"{file_name} added to the .gitignore file"
            repo = Repo('.')
            repo.index.add(".gitignore")
            repo.index.commit(commit_msg)


def write_modified_html_content(graph_html_content, html_fn):
    with open(html_fn, "w") as out:
        out.write(graph_html_content)


def set_html_content(net,
                     graph_config_names_list=None,
                     nodes_graph_config_obj_dict=None,
                     edges_graph_config_obj_dict=None,
                     graph_reduction_config_obj_dict=None,
                     graph_nodes_subset_config_obj_dict=None,
                     include_title=True):

    html_code = '''
        <div style="margin-left: 5px">
            <button class="btn btn-secondary btn-sm" onclick="refresh_graph()" type="button">
             <i class="bi bi-arrow-clockwise"></i>
            </button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="reset_graph()">Reset graph</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="fit_graph()">Fit graph</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="stop_animation()">Stop animation</button>
            <button type="button" class="btn btn-secondary btn-sm" id="right-click-hide-button" onclick="show_right_clicked_hidden_nodes()">Show hidden nodes</button>
            <button type="button" class="btn btn-secondary btn-sm collapsible_vertical_ttl">Display ttl content</button>
            <button type="button" class="btn btn-secondary btn-sm collapsible_vertical_menu">Menu</button>
            <button type="button" class="btn btn-secondary btn-sm collapsible_horizontal_legend">Legend</button>
            
            <div id="ttl_content" class="content_collapsible_vertical_ttl"></div>

        </div>
        
        <div style="display:flex;">
            <div style="display: flex;" id="menu_container" class="content_collapsible_vertical_menu">
                <div class="menu_item_first_left menu_item">
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
            '<div class="menu_item">'
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
            ''')
        html_code += '</div>'

    if graph_reduction_config_obj_dict is not None:
        html_code += (
            '<div class="menu_item">'
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
            '<div class="menu_item">'
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

        html_code += '</div>'

    html_code += '''
                </div>
            </div>
            
            <div style="display: flex;">
                    <div id="legend_container" class="content_collapsible_horizontal_legend"></div>
                <div id="mynetwork"></div>
            </div>
    '''

    # with open(html_fn) as template:
    #     soup = bs4.BeautifulSoup(template.read(), "html.parser")
    soup = bs4.BeautifulSoup(net.html, "html.parser")

    for center in soup('center'):
        center.decompose()

    mynetwork_tag = soup.body.find('div', id="mynetwork")
    html_code_bs4 = bs4.BeautifulSoup(html_code, 'html.parser')
    if include_title:
        newh1_str = '<h1>ODA Graph Export Quick-Look</h1>'
        newh1_tag = bs4.BeautifulSoup(newh1_str, 'html.parser')
        mynetwork_tag.insert_before(newh1_tag)
    mynetwork_tag.insert_before(html_code_bs4)
    mynetwork_tag.decompose()

    doctype_tag = bs4.Doctype('html')
    soup.insert(0, doctype_tag)

    # with open(html_fn, "w") as out:
    #     out.write(str(soup.prettify()))
    net.html = str(soup.prettify())


def add_js_click_functionality(net, graph_ttl_stream=None,
                               nodes_graph_config_obj_str=None,
                               edges_graph_config_obj_str=None,
                               graph_reductions_obj_str=None,
                               graph_nodes_subset_config_obj_str=None,
                               include_ttl_content_within_html=True):

    net.html = net.html.replace('drawGraph();', '')
    soup = bs4.BeautifulSoup(net.html, "html.parser")

    javascript_content = f'''
    // initialize global variables.
    var nodes_graph_config_obj = JSON.parse('{nodes_graph_config_obj_str}');
    var edges_graph_config_obj = JSON.parse('{edges_graph_config_obj_str}');
    var subset_nodes_config_obj = JSON.parse('{graph_nodes_subset_config_obj_str}');
    var graph_reductions_obj = JSON.parse('{graph_reductions_obj_str}');
    var graph_version = ``;
    '''
    if include_ttl_content_within_html:
        javascript_content += f'\nvar graph_ttl_content = `{graph_ttl_stream}`;'
    else:
        javascript_content += f'\nvar graph_ttl_content = ``;'

    javascript_content += '''
    
    var edges;
    var nodes;
    var network; 
    var container;
    var data;
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
    
    window.onload = function () {
        load_graph();
    };
    '''
    javascript_tag = soup.new_tag("script", type="application/javascript")
    javascript_tag.append(javascript_content)
    soup.head.append(javascript_tag)
    # if soup is not None:
        # with open(html_fn, "w") as outf:
        #     outf.write(str(soup.prettify()))
    net.html = str(soup.prettify())


def set_html_head(net):
    soup = bs4.BeautifulSoup(net.html, "html.parser")

    css_tag = soup.head.find('style', type="text/css")
    css_tag.decompose()

    new_script_rdflib_library = soup.new_tag("script", type="application/javascript",
                                             src="https://unpkg.com/n3/browser/n3.min.js")
    soup.head.append(new_script_rdflib_library)

    new_script_query_sparql_library = soup.new_tag("script", type="application/javascript",
                                                   src="https://rdf.js.org/comunica-browser/versions/latest"
                                                       "/engines/query-sparql-rdfjs/comunica-browser.js")
    soup.head.append(new_script_query_sparql_library)

    new_script_bootstrap_icons_css = soup.new_tag("link", rel="stylesheet",  type="text/css",
                                                   href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.3.0/font/bootstrap-icons.css")
    soup.head.append(new_script_bootstrap_icons_css)

    new_script_jquery_library = soup.new_tag("script", type="application/javascript",
                                             src="https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js")
    soup.head.append(new_script_jquery_library)

    graph_helper_library = soup.new_tag("script", type="application/javascript",
                                        src="https://odahub.io/renku-aqs-graph-library/graph_helper.js")
    soup.head.append(graph_helper_library)

    graph_helper_css = soup.new_tag("link", rel="stylesheet",  type="text/css",
                                    href="https://odahub.io/renku-aqs-graph-library/style.css")
    soup.head.append(graph_helper_css)

    bindings_lib_tag = soup.find('script', {"src": "lib/bindings/utils.js"})
    if bindings_lib_tag is not None:
        bindings_lib_tag["src"] = "../renku-aqs-graph-library/lib/bindings/utils.js"

    title_tag = soup.new_tag("title")
    title_tag.string = "Graph visualization"
    soup.head.append(title_tag)

    net.html = str(soup.prettify())
