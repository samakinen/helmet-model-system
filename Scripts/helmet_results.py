from emme_bindings.emme_project import EmmeProject
from assignment.emme_assignment import EmmeAssignmentModel
from datahandling.matrixdata import MatrixData
import parameters

def assign_volumes(emme_project, resultmatrices, first_scenario_id):
    """
    Assing volumes for last iteration round.
    """
    ass_model = EmmeAssignmentModel(emme_project, first_scenario_id)
    ass_classes = resultmatrices.list_matrices("demand", "aht")
    print ass_classes
    for tp in parameters.emme_scenario:
            print "Assigning period " + tp
            with resultmatrices.open("demand", tp) as mtx:
                base_demand = {ass_class: mtx[ass_class] for ass_class in ass_classes}
            ass_model.assign(tp, base_demand,  is_last_iteration = True) 

def link_day_volumes(emme_project, res_scen_id, attr):
    """ 
    Sums and expands link volumes from different scenarios
    to one result scenario.
    """
    emmebank = emme_project.modeller.emmebank
    extra_attr = parameters.link_volumes[attr]
    # get attr from different time periods to dictionary
    links_attr = {}
    for tp in parameters.emme_scenario:
        tp_attr = {}
        scenario = emmebank.scenario(parameters.emme_scenario[tp])
        network = scenario.get_network()
        for link in network.links():
            tp_attr[link.id] = link[extra_attr]
        links_attr[tp] = tp_attr
    # get result network
    scenario = emmebank.scenario(res_scen_id)
    network = scenario.get_network()
    # create attr to save volume
    extra_attr_day = str(parameters.link_volumes[attr]) + "_day"
    emme_project.create_extra_attribute(
            extra_attribute_type = "LINK",
            extra_attribute_name = extra_attr_day,
            extra_attribute_description = "day volumes from result scripts",
            overwrite = True,
            scenario = scenario)
    # save link volumes to result network
    for link in network.links():
        day_add_attr = 0
        for tp in parameters.emme_scenario:
             if link.id in links_attr[tp]:
                expansion_factor = parameters.volume_factors[attr][tp]
                add_attr = links_attr[tp][link.id]
                day_add_attr += add_attr * expansion_factor
        link[extra_attr_day] = day_add_attr
    scenario.publish_network(network)

emme_project_path = "C:\\Users\\FIAS34036\\helmet\\helmet-model-system\\sijo_HM31.emp"
result_matrices_path = "C:\\Users\\FIAS34036\\helmet\\system_results\\2016_full_1_iter\\Matrices"
emme_project = EmmeProject(emme_project_path)

#resultmatrices = MatrixData(result_matrices_path)
#assign_volumes(emme_project, resultmatrices, 19)

# expand volumes to 24h to assignment network
res_scen_id = 22
for attr in parameters.link_volumes:
    link_day_volumes(emme_project, res_scen_id, attr) 