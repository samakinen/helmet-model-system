from emme_bindings.emme_project import EmmeProject
from datahandling.matrixdata import MatrixData
import results.assignment_results as assign_results
import results.aggregate_matrices as aggregate_matrices
import parameters
import pandas as pd

emme_project_path = "C:\\Users\\FIAS34036\\helmet\\helmet-model-system\\sijo_HM31.emp"
result_matrices_path = "C:\\Users\\FIAS34036\\helmet\\system_results\\2016_full_10_round\\Matrices"
parameters_path = "C:\\Users\\FIAS34036\\helmet\\system_results\\Parameters"
result_path = "C:\\Users\\FIAS34036\\helmet\\system_results\\2016_full_10_round\\"


emme_project = EmmeProject(emme_project_path)
first_scenario_id = 19

"""
Assignment
"""

resultmatrices = MatrixData(result_matrices_path)
ass_classes = resultmatrices.list_matrices("demand", "aht")
#assign_results.assign_volumes(emme_project, resultmatrices, first_scenario_id)

"""
24h expansion of volumes on network
"""
# expand volumes to 24h to assignment network
for attr in parameters.link_volumes:
    assign_results.calc_link_day(emme_project, first_scenario_id, attr) 
    
assign_results.calc_segment_day(emme_project, first_scenario_id, "transit") 

""" 
Traffic counts comparisons
"""
assign_results.import_count_data(emme_project, parameters_path, first_scenario_id)
assign_results.print_count_data(emme_project, result_path)

aggregation_data = aggregate_matrices.read_file(emme_project, parameters_path, "aggregation_shares.csv")
aggregate_matrices.aggregate_trips_day(emme_project, first_scenario_id, ass_classes, resultmatrices, aggregation_data, result_path)