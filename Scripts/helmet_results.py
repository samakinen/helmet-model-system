from utils.config import Config
from emme_bindings.emme_project import EmmeProject
from datahandling.matrixdata import MatrixData
import results.assignment_analysis as assign_analysis
import results.matrix_operations as mtx_operations
import parameters
import pandas as pd
import numpy as np
from Tkinter import *
from tkFileDialog import *
import os
import openmatrix as omx

class Results:
    def __init__(self):
        """
        Open emmebank and matrices.
        """
        config = Config().read_from_file()
        self.user = os.path.expanduser('~')
        root = Tk()
        emme_project_path = config.EMME_PROJECT_PATH
        root.withdraw()
        try: 
            self.emme_project = EmmeProject(emme_project_path)
            print "Emme-project {}".format(emme_project_path)
        except: 
            print 'Could not open Emme-project'
        self.result_path = os.path.join(config.RESULTS_PATH, config.SCENARIO_NAME)
        self.matrices_path = os.path.join(self.result_path, "Matrices")
        try:
            self.resultmatrices = MatrixData(self.matrices_path)
            self.ass_classes = self.resultmatrices.list_matrices("demand", "aht")
            print "Demand matrices {}".format(self.ass_classes)
        except: 
            print 'Could not open matrix files from {}'.format(self.matrices_path)
        self.first_scenario_id = config.FIRST_SCENARIO_ID
        self.scenarios = {
            "aht": self.first_scenario_id + 2,
            "pt": self.first_scenario_id + 3,
            "iht": self.first_scenario_id + 4
            }
        emme_scenario = self.emme_project.modeller.emmebank.scenario(self.first_scenario_id + 2)
        self.zone_numbers = emme_scenario.zone_numbers
        assign_param = config.SCENARIO_NAME
        
    def assign(self):
        """
        Perform end assignment to emmebank.
        """
        assign_analysis.assign_volumes(
            self.emme_project, 
            self.resultmatrices, 
            self.first_scenario_id)

    def sum_auto_volumes_24h(self):
        """
        24h expansion of volumes on network.
        """
        # expand volumes to 24h to assignment network
        result_scenario_id = 20
        emmebank = self.emme_project.modeller.emmebank
        try:
            scenario = emmebank.scenario(result_scenario_id)
        except:
            print "Scenario id not found in current Emme-project"
        for result_attribute in parameters.link_volumes:
            assign_analysis.calc_link_day(
                self.emme_project, 
                self.scenarios,
                result_scenario_id, 
                result_attribute
                ) 
            print "Ready {}".format(result_attribute)

    def sum_transit_volumes_24h(self):
        """
        24h expansion of volumes on network.
        """
        # expand volumes to 24h to assignment network
        result_scenario_id = 20
        emmebank = self.emme_project.modeller.emmebank
        assign_analysis.calc_segment_link_day(
            self.emme_project, 
            self.scenarios,
            result_scenario_id
            ) 
        print "Ready: {}".format("transit volumes links")
        assign_analysis.calc_segment_node_day(
            self.emme_project, 
            self.scenarios,
            result_scenario_id
            )
        assign_analysis.calc_segment_day(
            self.emme_project, 
            self.scenarios,
            result_scenario_id
            )
        print "Ready: {}".format("transit boardings segments")
        
    def traffic_count(self):
        """ 
        Traffic counts comparisons
        """
        assign_analysis.import_count_data(self.emme_project, parameters_path, self.first_scenario_id)
        assign_analysis.print_count_data(self.emme_project, self.result_path)

    def read_omx_to_emme(self):
        """
        Read omx-files to Emme-projects.
        OMX-files and matrix id provided via user input.
        Overwrites matrices in Emme-project.
        """

        root = Tk()
        matrix_datapath = askopenfilename(
            filetypes=[('omx', '*.omx')],
            title='Choose omx-file containing matrices to read:',
            initialdir='%s/helmet/system-results' % (self.user)
            )
        root.withdraw()
        fname = os.path.basename(matrix_datapath)
        try:
            mtxfile = omx.open_file(matrix_datapath, "r")
            names = mtxfile.list_matrices()
            mtxs = {}
            for name in names:
                mtxs[name] = np.array(mtxfile[name])
                print "Succesfully loaded matrix {}".format(name)
        except:
            print 'Tables could not be read'
        mtx_operations.set_emmebank_matrices(self.emme_project, mtxs, fname)

    def sum_omx_24h(self):
        """
        Sum resultsmatrices over day with volume factors.
        Write to omx-files.
        """
        mtx_operations.mtx_to_24h(
            self.resultmatrices, 
            self.zone_numbers, 
            self.scenarios)
        print "Saved 24h demand matrices to: {}".format(self.matrices_path)

    def aggregate_mtx(self):
        """ 
        Sum results with input data. Input data must 
        include columns "sij2019", "aggregation", "share" delimited
        by whitespace.
        """
        mtxtype = raw_input('Choose matrix type (etc. demand, transit, transfers):')
        tp = raw_input('Choose time period (aht, iht, pt, day):')
        submatrices = self.resultmatrices.list_matrices(mtxtype, tp)
        print submatrices
        root = Tk()
        agg_datapath = askopenfilename(
            filetypes=[('txt', '*.txt')],
            title='Choose txt-file containing the aggregation:',
            initialdir='%s/helmet/system-results' % (self.user)
            )
        root.withdraw()
        nr_zones = len(self.zone_numbers)
        try:
            aggregation_data = pd.read_csv(
                agg_datapath, delim_whitespace=True, squeeze=False, 
                keep_default_na=False, na_values="", comment='#', header="infer"
                )
            print "Succesfully loaded agg data from {}".format(agg_datapath)
            mtxs = {}
            for submtx in submatrices:
                mtxs[submtx] = np.zeros((nr_zones, nr_zones))
            with self.resultmatrices.open(mtxtype, tp) as mtx:
                for name in submatrices:
                    mtxs[name] = mtx[name]
                    print "Succesfully loaded matrix {}".format(name)
        except:
            print 'Tables could not be read'
        colname = aggregation_data.columns[1]
        fname = "{}_{}_{}".format(colname, mtxtype, tp)
        mtx_operations.aggregate_matrix(aggregation_data, mtxs, self.result_path, self.zone_numbers, fname)

    def transit_modes_omx(self):
        emme_modes = ['b','g','m','p,t','w', 'r']
        no_mtx = len(emme_modes) * len(self.scenarios.keys())
        print "Reads {} matrices to Emme-project".format(no_mtx)
        while True:
            try:
                mtx_id = int(input("Matrix id save results:"))
                break
            except ValueError:
                print("Value should be a whole number.")
        mtxdict = {}
        for tp in self.scenarios:
            for emme_name in emme_modes:
                name = emme_name.replace(',', '')
                mtxdict[name] = {
                    'id':'mf' + str(mtx_id), 
                    'emme_mode':emme_name, 
                    'scenario':tp}
                mtx_id = mtx_id + 1
            mtx_operations.transit_mode_matrices(
                self.emme_project, 
                self.scenarios, 
                mtxdict)
            for name in mtxdict:
                mtxdict[name] = {'demand': mtx_operations.get_emme_matrix(self.emme_project, mtxdict[name]['id'])}
            mtx_operations.emme_matrices_to_omx(self.zone_numbers, self.resultmatrices, "transit", tp, mtxdict)

    def transfers_omx(self):
        select_limits = ['2,2','3,999']
        no_mtx = len(select_limits) * len(self.scenarios.keys())
        print "Reads {} matrices to Emme-project".format(no_mtx)
        while True:
            try:
                mtx_id = int(input("Matrix id save results:"))
                break
            except ValueError:
                print("Value should be a whole number.")
        mtxdict = {}
        for tp in self.scenarios:
            for limit in select_limits:
                name = 'transfers_' + limit.replace(',', '_')
                select_lower = int(limit.split(',')[0])
                select_upper = int(limit.split(',')[1])
                mtxdict[name] = {
                    'id':'mf' + str(mtx_id), 
                    'select_lower':select_lower, 
                    'select_upper':select_upper, 
                    'scenario':tp}
                mtx_id = mtx_id + 1
            mtx_operations.transfer_matrices(
                self.emme_project, 
                self.scenarios, 
                mtxdict)
            for name in mtxdict:
                mtxdict[name] = {'demand': mtx_operations.get_emme_matrix(self.emme_project, mtxdict[name]['id'])}
            mtx_operations.emme_matrices_to_omx(self.zone_numbers, self.resultmatrices, "transfers", tp, mtxdict)

    def delete_matrices(self):
        while True:
            try:
                lower_limit = int(input("Lower limit (id):"))
                upper_limit = int(input("Lower limit (id):"))
                mtxtype = raw_input("Matrix type (mo, md, mf, ms):")
                break
            except ValueError:
                print("Value should be a whole number.")
        mtx_operations.del_emmebank_matrices(self.emme_project, mtxtype, lower_limit, upper_limit)

def main():
    results = Results()
    while True:
        print "1. Clear Emme-project matrices"
        print "2. Read omx demand to Emme-project"
        print "11. Assign bike, traffic and transit for current Helmet-project"
        print "12. Expand Helmet-project auto volumes to 24h"
        print "13. Expand Helmet-project transit volumes to 24h"
        print "14. Compare assignment to external count data"
        print "21. Get transit modes to omx-files"
        print "22. Get transfer transit trips to omx-files"
        print "23. Expand demand matrices to 24h (save to omx)"
        print "24. Aggregate omx-matrix results"
        print "99. Quit"
        opt_chosen = int(input("Choose:"))
        if opt_chosen == 1: 
            results.delete_matrices()
        if opt_chosen == 2: 
            results.read_omx_to_emme()
        if opt_chosen == 11: 
            results.assign()
        if opt_chosen == 12: 
            results.sum_auto_volumes_24h()
        if opt_chosen == 13: 
            results.sum_transit_volumes_24h()
        if opt_chosen == 14: 
            results.traffic_count()
        if opt_chosen == 21: 
            results.transit_modes_omx()
        if opt_chosen == 22: 
            results.transfers_omx()
        if opt_chosen == 23: 
            results.sum_omx_24h()
        if opt_chosen == 24: 
            results.aggregate_mtx()
        if opt_chosen == 99:  
            break

main()