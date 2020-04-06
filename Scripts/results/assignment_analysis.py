from assignment.emme_assignment import EmmeAssignmentModel
import parameters
import os
import numpy as np
import pandas as pd

def assign_volumes(emme_project, resultmatrices, first_scenario_id):
    scenarios = {
        "aht": first_scenario_id + 2,
        "pt": first_scenario_id + 3,
        "iht": first_scenario_id + 4
        }
    """
    Assing volumes for last iteration round.
    """
    ass_classes = resultmatrices.list_matrices("demand", "aht")
    while True:
        try:
            no_matrices = len(scenarios.keys()) * len(ass_classes)
            print "Reads in {} matrices.".format(no_matrices)
            mtx_id = int(input("Matrix ids to hold demand matrices:"))
            break
        except ValueError:
            print("Value should be a whole number.") 
    for tp in scenarios:
        emme_mtx = {}
        for ass_class in parameters.emme_demand_mtx: #self.ass_classes
            emme_mtx[ass_class] = {
                "id": "mf" + str(mtx_id), 
                "description": ass_class + "_demand_" + tp}
            mtx_id = mtx_id + 1
        print "Assigning period " + tp
        ass_model = EmmeAssignmentModel(
            emme_context = emme_project, 
            first_scenario_id = first_scenario_id,
            demand_mtx=emme_mtx
            )
        with resultmatrices.open("demand", tp) as mtx:
            base_demand = {ass_class: mtx[ass_class] for ass_class in ass_classes}
        ass_model.assign(tp, base_demand,  is_last_iteration = True) 

def calc_link_day(emme_project, scenarios, result_scenario_id, attr):
    """ 
    Sums and expands link volumes from different scenarios
    to one result scenario.
    """
    emmebank = emme_project.modeller.emmebank
    extra_attr = parameters.link_volumes[attr]
    # get attr from different time periods to dictionary
    links_attr = {}
    for tp in scenarios:
        tp_attr = {}
        scenario = emmebank.scenario(scenarios[tp])
        network = scenario.get_network()
        for link in network.links():
            tp_attr[link.id] = link[extra_attr]
        links_attr[tp] = tp_attr
    # get result network
    scenario = emmebank.scenario(result_scenario_id)
    # create attr to save volume
    extra_attr_day = str(parameters.link_volumes[attr])
    emme_project.create_extra_attribute(
            extra_attribute_type = "LINK",
            extra_attribute_name = extra_attr_day,
            extra_attribute_description = "link day volumes",
            overwrite = True,
            scenario = scenario)
    network = scenario.get_network()
    # save link volumes to result network
    for link in network.links():
        day_add_attr = 0
        for tp in scenarios:
             if link.id in links_attr[tp]:
                expansion_factor = parameters.volume_factors[attr][tp]
                add_attr = links_attr[tp][link.id]
                day_add_attr += add_attr * expansion_factor
        link[extra_attr_day] = day_add_attr
    scenario.publish_network(network)

def calc_segment_link_day(emme_project, scenarios, result_scenario_id):
    """ 
    Sums and expands segment volumes to links from different scenario.
    """
    attr = "transit"
    extra_attr = "@" + attr
    emmebank = emme_project.modeller.emmebank
    # get attr from different time periods to dictionary
    links_attr = {}
    for tp in scenarios:
        tp_attr = {}
        scenario = emmebank.scenario(scenarios[tp])
        emme_project.create_extra_attribute(
            extra_attribute_type = "LINK",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit day volumes",
            overwrite = True,
            scenario = scenario)
        network = scenario.get_network()
        for link in network.links():
            voltr_segment = 0
            for segment in link.segments():
                voltr_segment += segment.transit_volume
            link[extra_attr] = voltr_segment
            tp_attr[link.id] = voltr_segment
        links_attr[tp] = tp_attr
        scenario.publish_network(network)
    # get result network
    scenario = emmebank.scenario(result_scenario_id)
    # create attr to save volume
    emme_project.create_extra_attribute(
            extra_attribute_type = "LINK",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit day volumes",
            overwrite = True,
            scenario = scenario)
    network = scenario.get_network()
    # save link volumes to result network
    for link in network.links():
        day_add_attr = 0
        for tp in scenarios:
             if link.id in links_attr[tp]:
                expansion_factor = parameters.volume_factors[attr][tp]
                add_attr = links_attr[tp][link.id]
                day_add_attr += add_attr * expansion_factor
        link[extra_attr] = day_add_attr
    scenario.publish_network(network)

def calc_segment_node_day(emme_project, scenarios, result_scenario_id):
    """ 
    Sums and expands node volumes to links from different scenario.
    """
    attr = "transit"
    extra_attr = "@" + attr + "_node"
    emmebank = emme_project.modeller.emmebank
    # get attr from different time periods to dictionary
    nodes_attr = {}
    for tp in scenarios:
        tp_attr = {}
        scenario = emmebank.scenario(scenarios[tp])
        emme_project.create_extra_attribute(
            extra_attribute_type = "NODE",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit boardings",
            overwrite = True,
            scenario = scenario)
        network = scenario.get_network()
        for node in network.nodes():
            board_segment = 0
            for segment in node.outgoing_segments():
                board_segment += segment.transit_boardings
            node[extra_attr] = board_segment
            tp_attr[node.id] = board_segment
        nodes_attr[tp] = tp_attr
        scenario.publish_network(network)
    # get result network
    scenario = emmebank.scenario(result_scenario_id)
    # create attr to save volume
    emme_project.create_extra_attribute(
            extra_attribute_type = "NODE",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit boardings 24h",
            overwrite = True,
            scenario = scenario)
    network = scenario.get_network()
    # save link volumes to result network
    for node in network.nodes():
        day_add_attr = 0
        for tp in scenarios:
             if node.id in nodes_attr[tp]:
                expansion_factor = parameters.volume_factors[attr][tp]
                add_attr = nodes_attr[tp][node.id]
                day_add_attr += add_attr * expansion_factor
        node[extra_attr] = day_add_attr
    scenario.publish_network(network)

def calc_segment_day(emme_project, scenarios, result_scenario_id):
    """ 
    Sums and expands node volumes to links from different scenario.
    """
    attr = "transit"
    extra_attr = "@" + attr + "_segment"
    emmebank = emme_project.modeller.emmebank
    # get attr from different time periods to dictionary
    segments_attr = {}
    for tp in scenarios:
        tp_attr = {}
        scenario = emmebank.scenario(scenarios[tp])
        emme_project.create_extra_attribute(
            extra_attribute_type = "TRANSIT_SEGMENT",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit boardings",
            overwrite = True,
            scenario = scenario)
        network = scenario.get_network()
        for segment in network.transit_segments():
            tp_attr[segment.id] = segment.transit_boardings
        segments_attr[tp] = tp_attr
    # get result network
    scenario = emmebank.scenario(result_scenario_id)
    # create attr to save volume
    emme_project.create_extra_attribute(
            extra_attribute_type = "TRANSIT_SEGMENT",
            extra_attribute_name = extra_attr,
            extra_attribute_description = "transit boardings 24h",
            overwrite = True,
            scenario = scenario)
    network = scenario.get_network()
    # save link volumes to result network
    for segment in network.transit_segments():
        day_add_attr = 0
        for tp in scenarios:
             if segment.id in segments_attr[tp]:
                expansion_factor = parameters.volume_factors[attr][tp]
                add_attr = segments_attr[tp][segment.id]
                day_add_attr += add_attr * expansion_factor
        segment[extra_attr] = day_add_attr
    scenario.publish_network(network)

def import_count_data(emme_project, parameters_path, first_scenario_id):
    scenarios = [
        first_scenario_id + 1, 
        first_scenario_id + 2, 
        first_scenario_id + 4
    ]
    scenarios_fnames = [
        "links_2016_vrk.txt", 
        "links_2016_aht.txt", 
        "links_2016_iht.txt"
        ]
    emmebank = emme_project.modeller.emmebank
    for i, j in zip(scenarios, scenarios_fnames):
        scenario_selection = emmebank.scenario(i)
        #data_explorer.replace_primary_scenario(scenario_selection)
        print i
        print j
        emme_project.create_extra_attribute(
            extra_attribute_type="LINK",
            extra_attribute_name="@l_count",
            extra_attribute_description="observed counts",
            overwrite=True,
            scenario = scenario_selection
            )
        emme_project.create_extra_attribute(
            extra_attribute_type="LINK",
            extra_attribute_name="@m_count",
            extra_attribute_description="observed counts",
            overwrite=True,
            scenario = scenario_selection
            )
        emme_project.create_extra_attribute(
            extra_attribute_type="LINK",
            extra_attribute_name="@l_count_type",
            extra_attribute_description="observed counts types",
            overwrite=True,
            scenario = scenario_selection
            )
        emme_project.create_extra_attribute(
            extra_attribute_type="LINK",
            extra_attribute_name="@direction",
            extra_attribute_description="observed counts direction",
            overwrite=True,
            scenario = scenario_selection
            )
        file_path = os.path.join(parameters_path, j).replace("\\","/")
        emme_project.import_attr(
            file_path,
            scenario = scenario_selection,
            field_separator=",",
            column_labels={0: "inode", 1: "jnode", 2: "@l_count", 3: "@l_count_type", 4: "@m_count", 5: "@direction"},
            revert_on_error=True
            )

def print_count_data(emme_project, result_path):
    scenarios = {"vrk": 20, "aht": 21, "iht": 23}
    emmebank = emme_project.modeller.emmebank
    # parameters
    l_scenario_id = []
    l_counts = []
    l_counts_types = []
    l_directions = []
    l_modes = []
    car_leisure = []
    car_work = []
    truck = []
    trailer_truck = []
    van = []
    bus = []
    m_scenario_id = []
    m_counts = []
    m_counts_types = []
    m_directions = []
    m_modes = []
    voltr = []

    for i in scenarios:
        scenario = emmebank.scenario(scenarios[i])
        network = scenario.get_network()
        #
        for link in network.links():
            if link['@l_count'] > 0:
                l_scenario_id.append(i)
                l_modes.append(link.modes)
                l_counts.append(link['@l_count'])
                l_counts_types.append(link['@l_count_type'])
                l_directions.append(link['@direction'])
                car_leisure.append(link['@car_leisure'])
                car_work.append(link['@car_work'])
                truck.append(link['@truck'])
                trailer_truck.append(link['@trailer_truck'])
                van.append(link['@van'])
                bus.append(link['@bus'])

            if link['@m_count'] > 0:
                m_scenario_id.append(i)
                m_modes.append(link.modes)
                m_counts.append(link['@m_count'])
                m_counts_types.append(link['@l_count_type'])
                m_directions.append(link['@direction'])
                voltr.append(link['@transit'])

        volau = (
            np.array(car_leisure) + 
            np.array(car_work) + 
            np.array(truck) + 
            np.array(trailer_truck) + 
            np.array(van) +
            np.array(bus)
            )
        
    l_d = {
        'scenario': l_scenario_id,
        'l_count': l_counts, 
        'l_count_type': l_counts_types, 
        'mode': [list(x) for x in l_modes],
        'direction': l_directions,
        'volau': volau
        } 

    m_d = {
        'scenario': m_scenario_id,
        'm_count': m_counts, 
        'l_count_type': m_counts_types, 
        'mode': [list(x) for x in m_modes],
        'direction': m_directions,
        'voltr': voltr
        } 
    
    l_df = pd.DataFrame(data = l_d)
    m_df = pd.DataFrame(data = m_d)

    modes = []
    for i in l_df["mode"].tolist():
        k = ""
        for j in i:
            k = k + str(j)
        modes.append(k)
    l_df["mode"] = modes

    modes = []
    for i in m_df["mode"].tolist():
        k = ""
        for j in i:
            k = k + str(j)
        modes.append(k)
    m_df["mode"] = modes

    directions_names = pd.DataFrame(data = {
        "direction": [1,
                    2,
                    3,
                    4],
        "direction_name": [u"Keskustaan",
                        u"Keskustasta",
                        u"Lanteen",
                        u"Itaan"]
    })
    l_count_names = pd.DataFrame(data = {
        "l_count_type":[1,2,3,4,5,6,7],
        "l_count_name":[u"Niemen raja", 
                        u"Kantakaupungin raja", 
                        u"Kaupungin raja", 
                        u"Poikittaislinja", 
                        u"Keha I", 
                        u"Keha II", 
                        u"Keha III"]
    })

    l_df = l_df.merge(l_count_names, on = "l_count_type", how='left')
    l_df = l_df.merge(directions_names, on = "direction", how='left')
    m_df = m_df.merge(l_count_names, on = "l_count_type", how='left')
    m_df = m_df.merge(directions_names, on = "direction", how='left')

    result_fname = os.path.join(result_path, "l_count_model.txt").replace("\\","/")
    l_df.to_csv(result_fname, index = False, sep='\t')

    result_fname = os.path.join(result_path, "m_count_model.txt").replace("\\","/")
    m_df.to_csv(result_fname, index = False, sep='\t')
    