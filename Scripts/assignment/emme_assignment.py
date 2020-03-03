import os
import numpy
import pandas
import parameters as param
from abstract_assignment import AssignmentModel, ImpedanceSource
from datatypes.car import Car
from datatypes.journey_level import JourneyLevel
from datatypes.path_analysis import PathAnalysis
from datahandling import resultdata


class EmmeAssignmentModel(AssignmentModel, ImpedanceSource):
    def __init__(self, emme_context, car_dist_cost=param.dist_cost, first_scenario_id=19):
        """
        first_scenario_id (bike scenario) is usually #19,
            followed by (#20) walk scenario, (#21) morning scenario, (#22) midday scenario, and (#23) evening scenario.
        If first scenario is set something else (e.g. #5), then following scenarios are also adjusted (#6, #7, #8, #9).
        Walk scenario is not calculated, so effective scenarios by convention are <first>, +2, +3, +4.
        """
        # TODO MON: consider rename as per emme.py comments. E.g. self.emme_project , because EMME's library allows for many interfaces e.g. TMGtools
        # y (prion jalkeen)
        self.emme = emme_context
        for mtx_type in param.emme_mtx:
            mtx = param.emme_mtx[mtx_type]
            for ass_class in mtx:
                self.emme.create_matrix(
                    matrix_id=mtx[ass_class]["id"],
                    matrix_name=mtx_type+"_"+ass_class,
                    matrix_description=mtx[ass_class]["description"],
                    default_value=0,
                    overwrite=True)
        self.dist_cost = car_dist_cost
        self.bike_scenario = first_scenario_id
        # +1 (unused) is walk scenario
        self.emme_scenario = {
            "aht": first_scenario_id+2,
            "pt": first_scenario_id+3,
            "iht": first_scenario_id+4,
        }
        for time_period in self.emme_scenario:
            self._create_attr(self.emme_scenario[time_period])
            self._calc_road_cost(self.emme_scenario[time_period])
            self._calc_boarding_penalties(self.emme_scenario[time_period])
            self._calc_background_traffic(self.emme_scenario[time_period])
        self._specify()
        self._has_assigned_bike_and_walk = False

    def assign(self, time_period, matrices, is_last_iteration=False, is_first_iteration=False):
        """Assign cars, bikes and transit for one time period.
        
        Parameters
        ----------
        time_period : str
            Time period (aht/pt/iht)
        matrices: dict
            Assignment class (car_work/transit/...) : numpy 2-d matrix
        is_last_iteration: bool
        is_first_iteration: bool
        """
        self.emme.logger.info("Assignment starts...")
        self.set_matrices(matrices)
        scen_id = self.emme_scenario[time_period]
        if not self._has_assigned_bike_and_walk:
            self._assign_pedestrians(scen_id)
            self._assign_bikes(param.bike_scenario,
                            param.emme_mtx["dist"]["bike"]["id"],
                            "all",
                            "@fvol_"+time_period)
            self._has_assigned_bike_and_walk = True
        if is_last_iteration:
            self._assign_cars(scen_id, param.stopping_criteria_fine)
            self._calc_extra_wait_time(scen_id)
            self._assign_congested_transit(scen_id)
            self._assign_bikes(param.bike_scenario,
                           param.emme_mtx["dist"]["bike"]["id"],
                           "all",
                           "@fvol_"+time_period)
        else:
            self._assign_cars(scen_id, param.stopping_criteria_coarse)
            self._calc_extra_wait_time(scen_id)
            self._assign_transit(scen_id)

    # TODO MON: If this is ALWAYS called after .assign(), could they be merged? Currently both re-route via emmebank, which is ambiguous.
    # TODO MON: Then the ABC class as well as MockAssignment would have to be adjusted respectively.
    # y
    def get_impedance(self, is_last_iteration=False):
        """Get travel impedance matrices for one time period from assignment.
        
        Return
        ------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit/...) : numpy 2-d matrix
        """
        mtxs = {"time": self.get_matrices("time"),
                "dist": self.get_matrices("dist"),
                "cost": self.get_matrices("cost")}
        mtxs["time"]["transit"] = self._damp(mtxs["time"]["transit"])
        mtxs["time"]["bike"] = mtxs["time"]["bike"].clip(None, 9999.)
        mtxs["time"]["car_work"] = self._extract_timecost_from_gcost("car_work")
        mtxs["time"]["car_leisure"] = self._extract_timecost_from_gcost("car_leisure")
        if not is_last_iteration:
            for ass_cl in ("car_work", "car_leisure"):
                mtxs["cost"][ass_cl] += self.dist_cost * mtxs["dist"][ass_cl]
        return mtxs

    # TODO MON: Could this emphasise "set_emmebank_matrices" ? and param "matrices" maybe "matrices_labels"
    # y (ei prio)
    def set_matrices(self, matrices):
        emmebank = self.emme.modeller.emmebank
        tmp_mtx = {
            "transit": 0,
            "bike": 0,
        }
        for mtx in matrices:
            mtx_label = mtx.split('_')[0]
            if mtx_label in tmp_mtx:
                idx = param.emme_mtx["demand"][mtx_label]["id"]
                tmp_mtx[mtx_label] += matrices[mtx]
                emmebank.matrix(idx).set_numpy_data(tmp_mtx[mtx_label])
            else:
                idx = param.emme_mtx["demand"][mtx]["id"]
                emmebank.matrix(idx).set_numpy_data(matrices[mtx])

    # TODO MON: Same as set_matrices. Although may be could be removed entirely if
    # TODO MON: return {subtype: self.get_matrix(mtx_type, subtype) for subtype in param.emme_mtx[mtx_type]}
    # y (ei prio)
    def get_matrices(self, mtx_type, time_period=None):
        """Get all matrices of specified type.
        
        Parameters
        ----------
        mtx_type : str
            Type (demand/time/transit/...)
        time_period: str
            (Unused currently)

        Return
        ------
        dict
            Subtype (car_work/truck/inv_time/...) : numpy 2-d matrix
                Matrix of the specified type
        """
        # TODO Remove freight impedance matrices from selection,
        # if not last iteration
        matrices = dict.fromkeys(param.emme_mtx[mtx_type].keys())
        for mtx in matrices:
            matrices[mtx] = self.get_matrix(mtx_type, mtx)
        return matrices

    def get_matrix(self, assignment_result_type, subtype):
        """Get matrix with type pair (e.g., demand, car_work).
        
        Parameters
        ----------
        assignment_result_type : str
            Type (demand/time/transit/...)
        subtype : str
            Subtype (car_work/truck/inv_time/...)

        Return
        ------
        numpy 2-d matrix
            Matrix of the specified type
        """
        emme_id = param.emme_mtx[assignment_result_type][subtype]["id"]
        return self.emme.modeller.emmebank.matrix(emme_id).get_numpy_data()

    # TODO MON: Should this indicate it's specificly "morning rush hour zone numbers in emme_project (emmebank)"?
    # aina samat, siksi aht. Long-term tarkoitus paasta naiden kovakoodauksesta eroon
    @property
    def zone_numbers(self):
        """Numpy array of all zone numbers.""" 
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(self.emme_scenario["aht"])
        return scen.zone_numbers

    # TODO MON: Same as zone_numbers property
    # aina samat, siksi aht
    @property
    def mapping(self):
        """dict: Dictionary of zone numbers and corresponding indices."""
        mapping = {}
        for idx, zone in enumerate(self.zone_numbers):
            mapping[zone] = idx
        return mapping

    # TODO MON: Same as zone_numbers property
    # aina samat, siksi aht
    @property
    def nr_zones(self):
        """int: Number of zones in assignment model."""
        return len(self.zone_numbers)

    def _damp(self, travel_time):
        """Reduce the impact from first waiting time on total travel time."""
        fwt = self.get_matrix("transit", "fw_time")
        wt_weight = param.waiting_time_perception_factor
        # Calculate transit travel time where first waiting time is damped
        dtt = travel_time + wt_weight*((5./3.*fwt)**0.8 - fwt)
        return dtt

    def _extract_timecost_from_gcost(self, ass_class):
        """Remove monetary cost from generalized cost."""
        # Traffic assignment produces a generalized cost matrix.
        # To get travel time, monetary cost is removed from generalized cost.
        vot_inv = param.vot_inv[param.vot_class[ass_class]]
        gcost = self.get_matrix("gen_cost", ass_class)
        tcost = self.get_matrix("cost", ass_class)
        tdist = self.get_matrix("dist", ass_class)
        return gcost - vot_inv *(tcost + self.dist_cost*tdist)

    def create_attribute(self, att, att_type, att_desc, scen_id):
        """Copy network attribute from scenario to another."""
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(scen_id)
        self.emme.create_extra_attribute(
            extra_attribute_type = att_type,
            extra_attribute_name = att,
            extra_attribute_description = att_desc,
            overwrite = True,
            scenario = scen)

    def sum_link_volumes(self, res_scen_id, attr):
        """ 
        Sums and expands link volumes from different scenarios
        to one result scenario.
        """
        emmebank = self.emme.modeller.emmebank
        # get attr to dictionary from different time periods
        links_attr = {}
        for tp in param.emme_scenario:
            tp_attr = {}
            scenario = emmebank.scenario(param.emme_scenario[tp])
            network = scenario.get_network()
            for link in network.links():
                extra_attr = param.link_volumes[attr]
                tp_attr[link.id] = link[extra_attr]
            links_attr[tp] = tp_attr
         # save to result network
        scenario = emmebank.scenario(res_scen_id)
        network = scenario.get_network()
        for tp in param.emme_scenario:
            for link in network.links():
                if link.id in links_attr[tp]:
                    add_attr = links_attr[tp][link.id]
                    expansion_factor = param.volume_factors[attr][tp]
                    extra_attr = param.link_volumes[attr]
                    link[extra_attr] = link[extra_attr] + add_attr * expansion_factor
        scenario.publish_network(network)
    
    def _create_attr(self, scen_id):
        """Create attributes needed in assignment."""
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(scen_id)
        # defined in params
        for attr in param.emme_attributes.keys():
            self.create_attribute(attr, param.emme_attributes[attr], "model calc", scen)

    def _calc_background_traffic(self, scen_id):
        """Calculate background traffic (buses)."""
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(scen_id)
        # Reset @vm1 to zero
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "transit_line": "all",
            },
            "expression": "0",
            "result": "@freq",
            "aggregation": None,
        }, scen)
        # Calculate number of line departures per hour
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "transit_line": "hdw=1,900",
            },
            "expression": "60.0/hdw",
            "result": "@freq",
            "aggregation": None,
        }, scen)
        # Reset @vm to zero
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": "all",
            },
            "expression": "0",
            "result": "@bus",
            "aggregation": None,
        }, scen)
        # Calculate number of link departures per hour
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": "all",
                "transit_line": "all"
            },
            "expression": "@freq",
            "result": "@bus",
            "aggregation": "+",
        }, scen)
        # Reset ul3 to zero
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": "all",
            },
            "expression": "0",
            "result": param.background_traffic,
            "aggregation": None,
        }, scen)
        # Set ul3 to @vm for links without bus lane
        self.emme.network_calc({
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": "vdf=1,5",
            },
            "expression": "@vm",
            "result": param.background_traffic,
            "aggregation": None,
        }, scen)

    def _calc_road_cost(self, scen_id):
        """Calculate road charges and driving costs for one scenario."""
        self.emme.logger.info("Calculates road charges for scenario " + str(scen_id))
        scenario = self.emme.modeller.emmebank.scenario(scen_id)
        network = scenario.get_network()
        for link in network.links():
            ruma = link.length * link["@hinta"]
            rumpi = self.dist_cost * link.length
            link['@ruma'] = ruma
            link["@rumsi"] = (ruma + rumpi)
        scenario.publish_network(network)
        
    def print_vehicle_kms(self):
        freight_classes = ["van", "truck", "trailer_truck"]
        vdfs = [1, 2, 3, 4, 5]
        transit_modes = {
            "bus": "bde",
            "trunk": "g",
            "metro": "m",
            "train": "rj",
            "tram": "tp",
        }
        kms = dict.fromkeys(freight_classes + ["car"])
        for ass_class in kms:
            kms[ass_class] = dict.fromkeys(vdfs, 0)
        transit_dists = dict.fromkeys(transit_modes, 0)
        transit_times = dict.fromkeys(transit_modes, 0)
        for tp in param.emme_scenario:
            scen_id = param.emme_scenario[tp]
            scenario = self.emme.modeller.emmebank.scenario(scen_id)
            network = scenario.get_network()
            for link in network.links():
                if link.volume_delay_func <= 5:
                    vdf = link.volume_delay_func
                else:
                    # Links with bus lane
                    vdf = link.volume_delay_func - 5
                if vdf in vdfs:
                    car_vol = link.auto_volume
                    for ass_class in freight_classes:
                        kms[ass_class][vdf] += (param.volume_factors[ass_class][tp]
                                                * link[param.link_volumes[ass_class]]
                                                * link.length)
                        car_vol -= link[param.link_volumes[ass_class]]
                    kms["car"][vdf] += (param.volume_factors["car"][tp] * car_vol * link.length)
            for line in network.transit_lines():
                for modes in transit_modes:
                    if line.mode.id in transit_modes[modes]:
                        mode = modes
                for segment in line.segments():
                    transit_dists[mode] += (param.volume_factors["transit"][tp]
                                            * line["@vm1"]
                                            * segment.link.length)
                    transit_times[mode] += (param.volume_factors["transit"][tp]
                                            * line["@vm1"]
                                            * segment.transit_time)
        for ass_class in kms:
            resultdata.print_data(
                kms[ass_class].values(), "vehicle_kms.txt",
                kms[ass_class].keys(), ass_class)
        resultdata.print_data(
            transit_dists.values(), "transit_kms.txt",
            transit_dists.keys(), "dist")
        resultdata.print_data(
            transit_times.values(), "transit_kms.txt",
            transit_times.keys(), "time")

    def calc_transit_cost(self, fares, peripheral_cost, default_cost=None):
        """Calculate transit zone cost matrix by performing 
        multiple transit assignments.
        
        Parameters
        ----------
        fares : pandas Dataframe
            Zone fare vector and fare exclusiveness vector
        peripheral_cost : numpy 2-d matrix
            Fixed cost matrix for peripheral zones
        default_cost : numpy 2-d matrix
            (optional) Fixed cost matrix to use instead of calculated cost
        """
        emmebank = self.emme.modeller.emmebank
        idx = param.emme_mtx["cost"]["transit"]["id"]
        if default_cost is not None:
            # Use fixed cost matrix
            emmebank.matrix(idx).set_numpy_data(default_cost)
            return

        scen_id = self.emme_scenario["aht"]
        # Move transfer penalty to boarding penalties,
        # a side effect is that it then also affects first boarding
        self._calc_boarding_penalties(scen_id, 5)
        scenario = emmebank.scenario(scen_id)
        has_visited = {}
        mapping = self.mapping
        network = scenario.get_network()
        transit_zones = set()
        for node in network.nodes():
            transit_zones.add(node.label)
        for transit_zone in transit_zones:
            # Set tag to 1 for nodes in transit zone and 0 elsewhere
            for node in network.nodes():
                node.data1 = (node.label == transit_zone)
            scenario.publish_network(network)
            # Transit assignment with zone tag as weightless boarding cost
            self._assign_transit(scen_id, True)
            nr_visits = self.get_matrix("transit", "board_cost")
            # If the number of visits is less than 1, there seems to
            # be an easy way to avoid visiting this transit zone
            has_visited[transit_zone] = (nr_visits >= 1)
        for centroid in network.centroids():
            # Add transit zone of destination to visited
            has_visited[centroid.label][:, mapping[centroid.number]] = True
        maxprice = 999
        cost = numpy.full_like(nr_visits, maxprice)
        mtx = next(iter(has_visited.values()))
        for zone_combination in fares["fare"]:
            goes_outside = numpy.full_like(mtx, False)
            for transit_zone in has_visited:
                # Check if the OD-flow has been at a node that is
                # outside of this zone combination
                if transit_zone not in zone_combination:
                    goes_outside |= has_visited[transit_zone]
            is_inside = ~goes_outside
            if zone_combination in fares["exclusive"]:
                # Calculate fares exclusive for municipality citizens
                zn = self.zone_numbers
                exclusion = pandas.DataFrame(is_inside, zn, zn)
                municipality = fares["exclusive"][zone_combination]
                inclusion = param.municipality[municipality]
                exclusion.loc[:inclusion[0]-1] = False
                exclusion.loc[inclusion[1]+1:] = False
                is_inside = exclusion.values
            zone_price = fares["fare"][zone_combination]
            # If OD-flow matches several combinations, pick cheapest
            cost[is_inside] = numpy.minimum(cost[is_inside], zone_price)
        # Calculate distance-based cost from inv-distance
        dist = self.get_matrix("dist", "transit")
        dist_cost = fares["start_fare"] + fares["dist_fare"]*dist
        cost[cost==maxprice] = dist_cost[cost==maxprice]
        # Replace fare for peripheral zones with fixed matrix
        bounds = param.areas["peripheral"]
        zn = pandas.Index(self.zone_numbers)
        l, u = zn.slice_locs(bounds[0], bounds[1])
        cost[l:u, :u] = peripheral_cost
        cost[:u, l:u] = peripheral_cost.T
        emmebank.matrix(idx).set_numpy_data(cost)
        # Reset boarding penalties
        self._calc_boarding_penalties(scen_id)

    def _specify(self):
        # Car assignment specification
        car_work = Car("car_work")
        car_leisure = Car("car_leisure")
        van = Car("van")
        truck = Car("truck", 0.2, "length")
        trailer_truck = Car("trailer_truck", 0.2, "length")
        self.car_spec = {
            "type": "SOLA_TRAFFIC_ASSIGNMENT",
            "classes": [
                car_work.spec,
                car_leisure.spec,
                trailer_truck.spec,
                truck.spec,
                van.spec,
            ],
            "background_traffic": {
                "link_component": param.background_traffic,
                "add_transit_vehicles": False,
            },
            "performance_settings": param.performance_settings,
            "stopping_criteria": None, # This is defined later
        }
        # Bike assignment specification
        self.bike_spec = {
            "type": "STANDARD_TRAFFIC_ASSIGNMENT",
            "classes": [ 
                {
                    "mode": param.bike_mode,
                    "demand": param.emme_mtx["demand"]["bike"]["id"],
                    "results": {
                        "od_travel_times": {
                            "shortest_paths": param.emme_mtx["time"]["bike"]["id"],
                        },
                        "link_volumes": None, # This is defined later
                    },
                    "analysis": {
                        "results": {
                            "od_values": None, # This is defined later
                        },
                    },
                }
            ],
            "path_analysis": PathAnalysis("ul3").spec,
            "stopping_criteria": {
                "max_iterations": 1,
                "best_relative_gap": 1,
                "relative_gap": 1,
                "normalized_gap": 1,
            },
            "performance_settings": param.performance_settings
        }  
        # Pedestrian assignment specification
        self.walk_spec = {
            "type": "STANDARD_TRANSIT_ASSIGNMENT",
            "modes": param.aux_modes,
            "demand": param.emme_mtx["demand"]["bike"]["id"],
            "waiting_time": {
                "headway_fraction": 0.01,
                "effective_headways": "hdw",
                "perception_factor": 0,
            },
            "boarding_time": {
                "penalty": 0,
                "perception_factor": 0,
            },
            "aux_transit_time": {
                "perception_factor": 1,
            },
            "od_results": {
                "transit_times": param.emme_mtx["time"]["walk"]["id"],
            },
            "strategy_analysis": {
                "sub_path_combination_operator": "+",
                "sub_strategy_combination_operator": "average",
                "trip_components": {
                    "aux_transit": "length",
                },
                "selected_demand_and_transit_volumes": {
                    "sub_strategies_to_retain": "ALL",
                    "selection_threshold": {
                        "lower": None,
                        "upper": None,
                    },
                },
                "results": {
                    "od_values": param.emme_mtx["dist"]["walk"]["id"],
                },
            },
        }
        # Transit assignment specification
        # Two journey levels are added at a later stage.
        # The two journey levels are identical, except that at the second
        # level an extra boarding penalty is implemented,
        # hence a transfer penalty. Waiting time length is also different. 
        # Walk only trips are not allowed.
        no_penalty = dict.fromkeys(["at_nodes", "on_lines", "on_segments"])
        no_penalty["global"] = {
            "penalty": 0, 
            "perception_factor": 1,
        }
        self.transit_spec = {
            "type": "EXTENDED_TRANSIT_ASSIGNMENT",
            "modes": param.transit_assignment_modes,
            "demand": param.emme_mtx["demand"]["transit"]["id"],
            "waiting_time": {
                "headway_fraction": param.standard_headway_fraction,
                "effective_headways": "hdw",
                "spread_factor": 1,
                "perception_factor": param.waiting_time_perception_factor
            },
            "boarding_time": {
                "global": None,
                "at_nodes": None,
                "on_lines": {
                    "penalty": "ut3",
                    "perception_factor": 1
                },
                "on_segments": param.extra_waiting_time,
            },
            # Boarding cost is defined for each journey level separately,
            # so here we just set the default to zero.
            "boarding_cost": no_penalty,
            "in_vehicle_time": {
                "perception_factor": 1
            },
            "aux_transit_time": param.aux_transit_time,
            "flow_distribution_at_origins": {
                "choices_at_origins": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_at_regular_nodes_with_aux_transit_choices": {
                "choices_at_regular_nodes": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_between_lines": {
                "consider_total_impedance": False
            },
            "journey_levels": None,
            "performance_settings": param.performance_settings,
        }
        # Transit assignment result specification
        mtx = param.emme_mtx
        self.transit_result_spec = {
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
            "total_impedance": mtx["time"]["transit"]["id"],
            "actual_first_waiting_times": mtx["transit"]["fw_time"]["id"],
            "actual_total_waiting_times": mtx["transit"]["tw_time"]["id"],
            "by_mode_subset": {
                "modes": param.transit_modes,
                "distance": mtx["dist"]["transit"]["id"],
                "avg_boardings": mtx["transit"]["num_board"]["id"],
                "actual_total_boarding_times": mtx["transit"]["board_time"]["id"],
                "actual_in_vehicle_times": mtx["transit"]["inv_time"]["id"],
                "actual_aux_transit_times": mtx["transit"]["aux_time"]["id"],
            },
        }

    def _assign_cars(self, scen_id, stopping_criteria):
        """Perform car_work traffic assignment for one scenario."""
        emmebank = self.emme.modeller.emmebank
        scenario = emmebank.scenario(scen_id)
        function_file = os.path.join(self.emme.path, param.func_car) # TODO refactor paths out from here
        self.emme.process_functions(function_file)
        self.emme.logger.info("Car assignment started...")
        self.car_spec["stopping_criteria"] = stopping_criteria
        self.emme.car_assignment(self.car_spec, scenario)
        self.emme.logger.info("Car assignment performed for scenario " 
                        + str(scen_id))
    
    def _assign_bikes(self, scen_id, length_mat_id, length_for_links, link_vol):
        """Perform bike traffic assignment for one scenario."""
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(scen_id)
        # TODO MON: Do these reside in the template emme project or what? .in files; self.emme.path forwards to emmebank path
        # ovat runkoprojektissa mukana
        function_file = os.path.join(self.emme.path, param.func_bike)  # TODO refactor paths out from here
        self.emme.process_functions(function_file)
        spec = self.bike_spec
        spec["classes"][0]["results"]["link_volumes"] = link_vol
        spec["classes"][0]["analysis"]["results"]["od_values"] = length_mat_id
        # Reset ul3 to zero
        netw_spec = {
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": "all",
            },
            "expression": "0",
            "result": spec["path_analysis"]["link_component"],
            "aggregation": None,
        }
        self.emme.network_calc(netw_spec, scen)
        # Define for which links to calculate length and save in ul3
        netw_spec = {
            "type": "NETWORK_CALCULATION",
            "selections": {
                "link": length_for_links,
            },
            "expression": "length",
            "result": spec["path_analysis"]["link_component"],
            "aggregation": None,
        }
        self.emme.network_calc(netw_spec, scen)
        self.emme.logger.info("Bike assignment started")
        self.emme.bike_assignment(specification=spec, scenario=scen)
        self.emme.logger.info("Bike assignment performed for scenario "
                        + str(scen_id))
    
    def _assign_pedestrians(self, scen_id):
        """Perform pedestrian assignment for one scenario."""
        emmebank = self.emme.modeller.emmebank
        scen = emmebank.scenario(scen_id)
        self.emme.logger.info("Pedestrian assignment started")
        self.emme.pedestrian_assignment(
            specification=self.walk_spec, scenario=scen)
        self.emme.logger.info("Pedestrian assignment performed for scenario "
                              + str(scen_id))

    def _calc_boarding_penalties(self, scen_id, extra_penalty=0):
        """Calculate boarding penalties for transit assignment."""
        emmebank = self.emme.modeller.emmebank
        scenario = emmebank.scenario(scen_id)
        # Definition of line specific boarding penalties
        netw_specs = []
        # Bus
        for mode in param.boarding_penalty:
            netw_specs.append({
                "type": "NETWORK_CALCULATION",
                "selections": {
                    "transit_line": "mode=" + mode,
                },
                "expression": str(param.boarding_penalty[mode]) + "+" + str(extra_penalty),
                "result": "ut3",
                "aggregation": None,
            })
        self.emme.network_calc(netw_specs, scenario)
        
    def _calc_extra_wait_time(self, scen_id):
        """Calculate extra waiting time for one scenario."""
        emmebank = self.emme.modeller.emmebank
        scenario = emmebank.scenario(scen_id)
        network = scenario.get_network()
        # Calculation of cumulative line segment travel time and speed
        self.emme.logger.info("Calculates cumulative travel times for scenario "
                         + str(scen_id))
        for line in network.transit_lines():
            cumulative_length = 0
            cumulative_time = 0
            cumulative_speed = 0
            headway_sd = 0
            for segment in line.segments():
                cumulative_length += segment.link.length
                # Travel time for buses in mixed traffic
                if segment.transit_time_func == 1:
                    cumulative_time += (segment.data2 * segment.link.length
                                        # + segment.link["@timau"]
                                        + segment.link.auto_time
                                        + segment.dwell_time)
                # Travel time for buses on bus lanes
                if segment.transit_time_func == 2:
                    cumulative_time += (segment.data2 * segment.link.length
                                        + segment.dwell_time)
                # Travel time for trams AHT
                if segment.transit_time_func == 3:
                    speedstr = str(int(segment.link.data1))
                    # Digits 5-6 from end (1-2 from beg.) represent AHT
                    # speed. If AHT speed is less than 10, data1 will 
                    # have only 5 digits.
                    speed = int(speedstr[:-4])
                    cumulative_time += ((segment.link.length / speed) * 60
                                        + segment.dwell_time)
                # Travel time for trams PT
                if segment.transit_time_func == 4:
                    speedstr = str(int(segment.link.data1))
                    # Digits 3-4 from end represent PT speed.
                    speed = int(speedstr[-4:-2])
                    cumulative_time += ((segment.link.length / speed) * 60
                                        + segment.dwell_time)
                # Travel time for trams IHT
                if segment.transit_time_func == 5:
                    speedstr = str(int(segment.link.data1))
                    # Digits 1-2 from end represent IHT speed.
                    speed = int(speedstr[-2:])
                    cumulative_time += ((segment.link.length / speed) * 60
                                        + segment.dwell_time)
                if cumulative_time > 0:
                    cumulative_speed = (cumulative_length
                                        / cumulative_time
                                        * 60)
                # Headway standard deviation for buses and trams
                if line.mode.id in param.headway_sd_func:
                    b = param.headway_sd_func[line.mode.id]
                    headway_sd = (b["asc"]
                                  + b["ctime"]*cumulative_time
                                  + b["cspeed"]*cumulative_speed)
                # Estimated waiting time addition caused by headway deviation
                segment["@wait_time_dev"] = headway_sd**2 / (2.0*line.headway)
        scenario.publish_network(network)

    def _assign_transit(self, scen_id, count_zone_boardings=False):
        """Perform transit assignment for one scenario."""
        if count_zone_boardings:
            jlevel1 = JourneyLevel(False, True)
            jlevel2 = JourneyLevel(True, True)
            bcost_spec = {
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "by_mode_subset": {
                    "modes": param.transit_modes,
                    "distance": param.emme_mtx["dist"]["transit"]["id"],
                    "actual_total_boarding_costs": param.emme_mtx["transit"]["board_cost"]["id"],
                },
            }
        else:
            jlevel1 = JourneyLevel(boarded=False)
            jlevel2 = JourneyLevel(boarded=True)
        self.transit_spec["journey_levels"] = [jlevel1.spec, jlevel2.spec]
        # self.transit_spec["boarding_cost"] = bcost
        emmebank = self.emme.modeller.emmebank
        scenario = emmebank.scenario(scen_id)
        self.emme.logger.info("Transit assignment started")
        self.emme.transit_assignment(self.transit_spec, scenario)
        if count_zone_boardings:
            self.emme.matrix_results(bcost_spec, scenario)
        else:
            self.emme.matrix_results(self.transit_result_spec, scenario)
        self.emme.logger.info("Transit assignment performed for scenario {}".format(str(scen_id)))

    def _assign_congested_transit(self, scen_id):
        """Perform congested transit assignment for one scenario."""
        emmebank = self.emme.modeller.emmebank
        scenario = emmebank.scenario(scen_id)
        self.emme.logger.info("Congested transit assignment started")
        self.emme.congested_assignment(
            transit_assignment_spec=self.transit_spec,
            congestion_function=param.trass_func,
            stopping_criteria=param.trass_stop,
            log_worksheets=False, scenario=scenario)
        self.emme.matrix_results(self.transit_result_spec, scenario)
        self.emme.logger.info("Transit assignment performed for scenario {}".format(str(scen_id)))
