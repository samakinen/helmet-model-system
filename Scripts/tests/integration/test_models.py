import unittest

import logging
import os
import numpy
import datahandling.resultdata as result
from assignment.mock_assignment import MockAssignmentModel
import assignment.departure_time as dt
from datahandling.zonedata import ZoneData
from datahandling.matrixdata import MatrixData
from demand.freight import FreightModel
from demand.trips import DemandModel
from demand.external import ExternalModel
from transform.impedance_transformer import ImpedanceTransformer
from datatypes.demand import Demand
import parameters

class ModelTest(unittest.TestCase):
    
    def test_models(self):
        print("Testing assignment..")
        zdata_base = ZoneData("2016_test")
        zdata_forecast = ZoneData("2030_test")
        basematrices = MatrixData("base_test")
        dm = DemandModel(zdata_forecast)
        dm.create_population()
        fm = FreightModel(zdata_base, zdata_forecast, basematrices)
        trucks = fm.calc_freight_traffic("truck")
        trailer_trucks = fm.calc_freight_traffic("trailer_truck")
        costs = MatrixData("2016_test")
        ass_model = MockAssignmentModel(costs)
        em = ExternalModel(basematrices, zdata_forecast, ass_model.zone_numbers)
        dtm = dt.DepartureTimeModel(ass_model.nr_zones)
        imptrans = ImpedanceTransformer()
        ass_classes = dict.fromkeys(parameters.emme_mtx["demand"].keys())

        self.assertEqual(7, len(ass_classes))

        impedance = {}
        for tp in parameters.emme_scenario:
            base_demand = {}
            basematrices.open_file("demand", tp)
            for ass_class in ass_classes:
                base_demand[ass_class] = basematrices.get_data(ass_class)
            basematrices.close()
            basematrices.open_file("cost", "peripheral")
            periph_cost = basematrices.get_data("transit")
            basematrices.close()
            ass_model.assign(tp, base_demand)
            if tp == "aht":
                ass_model.calc_transit_cost(zdata_forecast.transit_zone, periph_cost)
            impedance[tp] = ass_model.get_impedance()
            print("Validating impedance")
            self.assertEqual(3, len(impedance[tp]))
            self.assertIsNotNone(impedance[tp]["time"])
            self.assertIsNotNone(impedance[tp]["cost"])
            self.assertIsNotNone(impedance[tp]["dist"])
            
        print("Adding demand and assigning")

        dtm.add_demand(trucks)
        dtm.add_demand(trailer_trucks)
        for purpose in dm.tour_purposes:
            purpose_impedance = imptrans.transform(purpose, impedance)
            if purpose.name == "hoo":
                l, u = next(iter(purpose.sources)).bounds
                nr_zones = u - l
                purpose.generate_tours()
                for mode in purpose.model.dest_choice_param:
                    for i in xrange(0, nr_zones):
                        demand = purpose.distribute_tours(mode, purpose_impedance[mode], i)
                        dtm.add_demand(demand)
            else:
                demand = purpose.calc_demand(purpose_impedance)
                for mode in demand:
                    self._validate_demand(demand[mode])
                if purpose.dest != "source":
                    for mode in demand:
                        dtm.add_demand(demand[mode])
        for mode in parameters.external_modes:
            if mode == "truck":
                int_demand = trucks.matrix.sum(0) + trucks.matrix.sum(1)
            elif mode == "trailer_truck":
                int_demand = trailer_trucks.matrix.sum(0) + trailer_trucks.matrix.sum(1)
            else:
                int_demand = numpy.zeros(zdata_base.nr_zones)
                for purpose in dm.tour_purposes:
                    if purpose.dest != "source":
                        if purpose.name == "hoo":
                            l, u = next(iter(purpose.sources)).bounds
                        else:
                            l, u = purpose.bounds
                        int_demand[l:u] += purpose.generated_tours[mode]
                        int_demand += purpose.attracted_tours[mode]
            ext_demand = em.calc_external(mode, int_demand)
            dtm.add_demand(ext_demand)
        purpose_impedance = imptrans.transform(dm.purpose_dict["hoo"], impedance)
        # for person in dm.population:
        #     for tour in person.tours:
        #         tour.choose_mode()
        #         tour.choose_destination(purpose_impedance)
        #         dtm.add_demand(tour)
        impedance = {}
        for tp in parameters.emme_scenario:
            dtm.add_vans(tp, zdata_forecast.nr_zones)
            ass_model.assign(tp, dtm.demand[tp])
            impedance[tp] = ass_model.get_impedance()
            if tp == "aht":
                car_time = numpy.ma.average(impedance[tp]["time"]["car_work"],
                                            axis=1,
                                            weights=dtm.demand[tp]["car_work"])
                transit_time = numpy.ma.average(impedance[tp]["time"]["transit"],
                                                axis=1,
                                                weights=dtm.demand[tp]["transit"])
                time_ratio = transit_time / car_time
                result.print_data(time_ratio, "impedance_ratio.txt", ass_model.zone_numbers, "time")
                car_cost = numpy.ma.average(impedance[tp]["cost"]["car_work"],
                                            axis=1,
                                            weights=dtm.demand[tp]["car_work"])
                transit_cost = numpy.ma.average(impedance[tp]["cost"]["transit"],
                                                axis=1,
                                                weights=dtm.demand[tp]["transit"])
                cost_ratio = transit_cost / 44 / car_cost
                result.print_data(cost_ratio, "impedance_ratio.txt", ass_model.zone_numbers, "cost")
        dtm.init_demand()
        self.assertEquals(len(parameters.emme_scenario), len(impedance))
        self._validate_impedances(impedance["aht"])
        self._validate_impedances(impedance["pt"])
        self._validate_impedances(impedance["iht"])
        
        print("Assignment test done")
    
    def _validate_impedances(self, impedances):
        self.assertIsNotNone(impedances)
        self.assertIs(type(impedances), dict)
        self.assertEquals(len(impedances), 3)
        self.assertIsNotNone(impedances["time"])
        self.assertIsNotNone(impedances["cost"])
        self.assertIsNotNone(impedances["dist"])
        self.assertIs(type(impedances["time"]), dict)
        self.assertEquals(len(impedances["time"]), 5)
        self.assertIsNotNone(impedances["time"]["transit"])
        self.assertIs(type(impedances["time"]["transit"]), numpy.ndarray)
        self.assertEquals(impedances["time"]["transit"].ndim, 2)
        self.assertEquals(len(impedances["time"]["transit"]), 8)

    def _validate_demand(self, demand):
        self.assertIsNotNone(demand)
        self.assertIsNotNone(demand)
        self.assertIsInstance(demand, Demand)
        self.assertIs(type(demand.matrix), numpy.ndarray)
        self.assertEquals(demand.matrix.ndim, 2)
        self.assertEquals(demand.matrix.shape[1], 6)
        