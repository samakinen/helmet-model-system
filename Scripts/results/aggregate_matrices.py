from assignment.emme_assignment import EmmeAssignmentModel
import parameters
import os
import numpy as np
import pandas as pd

def print_aggregated_data(data, data_dir, filename):
    # data parameter is pandas data frame object
    filepath = os.path.join(data_dir, filename)
    data.to_csv(filepath, sep='\t', float_format="%1.5f")

def read_file(emme_project, data_dir, file_name):
    emmebank = emme_project.modeller.emmebank
    scen = emmebank.scenario(21)
    zone_numbers = scen.zone_numbers

    path = os.path.join(data_dir, file_name)
    data = pd.read_csv(
        path, delim_whitespace=True, squeeze=False, keep_default_na=False,
        na_values="", comment='#', header="infer")
    return data

def aggregate_trips_day(emme_project, first_scenario_id, ass_classes, resultmatrices, aggregation_data, data_dir):
    emmebank = emme_project.modeller.emmebank
    scen = emmebank.scenario(first_scenario_id)
    scenarios = {
        "aht": first_scenario_id + 2,
        "pt": first_scenario_id + 3,
        "iht": first_scenario_id + 4
        }
    zone_numbers = scen.zone_numbers
    nr_zones = len(zone_numbers)
    # sum full day trips and aggregate
    # day matrix using parameters volume_factors
    assign_mtx_day = {}
    for ass_class in ass_classes:
        assign_mtx_day[ass_class] = np.zeros((nr_zones, nr_zones))
    for tp in scenarios:
        with resultmatrices.open("demand", tp) as mtx:
            for ass_class in ass_classes:
                coeff =  parameters.volume_factors[ass_class][tp]
                assign_mtx_day[ass_class] += coeff * mtx[ass_class]
    # load aggregation shares and sum for new zones
    if aggregation_data is not None:
        aggregation_data = aggregation_data.reset_index()
        dest = zone_numbers
        orig = zone_numbers
        for mode_keys in assign_mtx_day.keys():
            mtx = pd.DataFrame(assign_mtx_day[mode_keys], orig, dest)
            mtx = mtx.reset_index().melt(id_vars = 'index')
            mtx.columns = ['orig', 'dest', 'value']
            aggregation_data.columns = ['index', 'orig', 'orig_agg', 'orig_share']
            mtx = mtx.merge(aggregation_data, on='orig', how='left')
            aggregation_data.columns = ['index', 'dest', 'dest_agg', 'dest_share']
            mtx = mtx.merge(aggregation_data, on='dest', how='left')
            mtx['value'] = mtx['value'] * mtx['orig_share'] * mtx['dest_share']
            mtx_agg = mtx.groupby(['orig_agg', 'dest_agg'])['value'].sum().reset_index()
            fname0 = "aggregated_trips_" + str(mode_keys) + ".txt"
            print_aggregated_data(mtx_agg, data_dir, fname0)