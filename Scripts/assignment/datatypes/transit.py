import parameters.assignment as param
from assignment.datatypes.path_analysis import PathAnalysis
from assignment.datatypes.journey_level import JourneyLevel


class TransitSpecification:
    """
    Transit assignment specification.
    
    Two journey levels are added at a later stage.
    At the second level an extra boarding penalty is implemented,
    hence a transfer penalty. Waiting time length is also different. 
    Walk only trips are not allowed.

    Parameters
    ----------
    ass_class : str
        Assignment class (transit_work/transit_leisure)
    demand_mtx : dict
        key : str
            Assignment class (transit_work/transit_leisure)
        value : dict
            id : str
                Emme matrix id
            description : dict
                Matrix description
    result_mtx : dict
        key : str
            Impedance type (time/cost/dist)
        value : dict
            key : str
                Assignment class (transit_work/transit_leisure)
            value : dict
                id : str
                    Emme matrix id
                description : dict
                    Matrix description
    count_zone_boardings : bool (optional)
        Whether assignment is performed only to count fare zone boardings
    is_last_iteration : bool (optional)
        If this is the last iteration, some other assignment parameters can be defined
    """
    def __init__(self, ass_class, demand_mtx, result_mtx, count_zone_boardings=False, is_last_iteration=False):
        self.demand_mtx = demand_mtx
        self.result_mtx = result_mtx
        no_penalty = dict.fromkeys(["at_nodes", "on_lines", "on_segments"])
        no_penalty["global"] = {
            "penalty": 0, 
            "perception_factor": 1,
        }
        self.transit_spec = {
            "type": "EXTENDED_TRANSIT_ASSIGNMENT",
            "modes": param.transit_assignment_modes,
            "demand": self.demand_mtx[ass_class]["id"],
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

        self.ntw_results_spec = {
            "type": "EXTENDED_TRANSIT_NETWORK_RESULTS",
            "on_segments": {
                "transit_volumes": "@{}_vol".format(ass_class),
                "total_boardings": "@{}_boa".format(ass_class),
                "transfer_boardings": "@{}_trb".format(ass_class),
                }
            }
        if count_zone_boardings:
            jlevel1 = JourneyLevel(boarded=False, ass_class=ass_class, count_zone_boardings=True)
            jlevel2 = JourneyLevel(boarded=True, ass_class=ass_class, count_zone_boardings=True)
            mtx_results_spec = {
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "by_mode_subset": {
                    "modes": param.transit_modes,
                    "distance": self.result_mtx["dist"][ass_class]["id"],
                    "actual_total_boarding_costs": self.result_mtx["trip_part"][ass_class + "_board_cost"]["id"],
                },
            }
        else:
            jlevel1 = JourneyLevel(boarded=False, ass_class=ass_class, is_last_iteration=is_last_iteration)
            jlevel2 = JourneyLevel(boarded=True, ass_class=ass_class, is_last_iteration=is_last_iteration)
            mtx_results_spec = {
                "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
                "total_impedance": self.result_mtx["time"][ass_class]["id"],
                "actual_first_waiting_times": self.result_mtx["trip_part"][ass_class + "_fw_time"]["id"],
                "actual_total_waiting_times": self.result_mtx["trip_part"][ass_class + "_tw_time"]["id"],
                "by_mode_subset": {
                    "modes": param.transit_assignment_modes,
                    "distance": self.result_mtx["dist"][ass_class]["id"],
                    "avg_boardings": self.result_mtx["trip_part"][ass_class + "_num_board"]["id"],
                    "actual_total_boarding_times": self.result_mtx["trip_part"][ass_class + "_board_time"]["id"],
                    "actual_in_vehicle_times": self.result_mtx["trip_part"][ass_class + "_inv_time"]["id"],
                    "actual_aux_transit_times": self.result_mtx["trip_part"][ass_class + "_aux_time"]["id"],
                },
            }

        self.transit_spec["journey_levels"] = [jlevel1.spec, jlevel2.spec]
        self.transit_result_spec = mtx_results_spec

