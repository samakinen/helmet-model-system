from argparse import ArgumentParser
import os

from utils.config import Config
import utils.log as log
from assignment.emme_assignment import EmmeAssignmentModel
from datahandling.matrixdata import MatrixData
from datahandling.zonedata import ZoneData
from assignment.emme_bindings.emme_project import EmmeProject
import parameters.assignment as param


def main(args):
    base_zonedata_path = os.path.join(args.baseline_data_path, "2016_zonedata")
    base_matrices_path = os.path.join(args.baseline_data_path, "base_matrices")
    emme_paths = args.emme_paths
    first_scenario_ids = args.first_scenario_ids
    forecast_zonedata_paths = args.forecast_data_paths

    if not emme_paths:
        msg = "Missing required argument 'emme-paths'."
        log.error(msg)
        raise ValueError(msg)
    if not first_scenario_ids:
        msg = "Missing required argument 'first-scenario-ids'."
        log.error(msg)
        raise ValueError(msg)
    if not forecast_zonedata_paths:
        msg = "Missing required argument 'forecast-zonedata-paths'."
        log.error(msg)
        raise ValueError(msg)
    # Check arg lengths
    if not (len(emme_paths) == len(first_scenario_ids)):
        msg = ("Non-matching number of emme-paths (.emp files) "
               + "vs. number of first-scenario-ids")
        log.error(msg)
        raise ValueError(msg)
    if not (len(emme_paths) == len(forecast_zonedata_paths)):
        msg = ("Non-matching number of emme-paths (.emp files) "
               + "vs. number of forecast-zonedata-paths")
        log.error(msg)
        raise ValueError(msg)

    # Check basedata input
    log.info("Checking base inputdata...")
    # Check filepaths (& first .emp path for zone_numbers in base zonedata)
    if not os.path.exists(base_zonedata_path):
        msg = "Baseline zonedata directory '{}' does not exist.".format(
            base_zonedata_path)
        log.error(msg)
        raise ValueError(msg)
    if not os.path.exists(base_matrices_path):
        msg = "Baseline matrices' directory '{}' does not exist.".format(
            base_matrices_path)
        log.error(msg)
        raise ValueError(msg)
    if not os.path.isfile(emme_paths[0]):
        msg = ".emp project file not found in given '{}' location.".format(
            emme_paths[0])
        log.error(msg)
        raise ValueError(msg)
    # Check base zonedata
    assignment_model = EmmeAssignmentModel(
        EmmeProject(emme_paths[0]), first_scenario_id=first_scenario_ids[0])
    base_zonedata = ZoneData(base_zonedata_path, assignment_model.zone_numbers)
    # Check base matrices
    matrixdata = MatrixData(base_matrices_path)
    for tp in assignment_model.emme_scenarios:
        with matrixdata.open("demand", tp, assignment_model.zone_numbers) as mtx:
            for ass_class in param.transport_classes:
                a = mtx[ass_class]

    # Check scenario based input data
    log.info("Checking base zonedata & scenario-based input data...")
    for i, emp_path in enumerate(emme_paths):
        log.info("Checking input data for scenario #{} ...".format(i))

        # Check filepaths
        if not os.path.isfile(emp_path):
            msg = ".emp project file not found in given '{}' location.".format(
                emp_path)
            log.error(msg)
            raise ValueError(msg)
        if not os.path.exists(forecast_zonedata_paths[i]):
            msg = "Forecast data directory '{}' does not exist.".format(
                forecast_zonedata_paths[i])
            log.error(msg)
            raise ValueError(msg)

        # Check forecasted zonedata
        forecast_zonedata = ZoneData(
            forecast_zonedata_paths[i], assignment_model.zone_numbers)

    log.info("Successfully validated all input files")


if __name__ == "__main__":
    # Initially read defaults from config file ("dev-config.json")
    # but allow override via command-line arguments
    config = Config().read_from_file()
    parser = ArgumentParser(epilog="HELMET model system entry point script.")
    # Logging
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
        default=config.LOG_LEVEL,
    )
    parser.add_argument(
        "--log-format",
        dest="log_format",
        choices={"TEXT", "JSON"},
        default=config.LOG_FORMAT,
    )
    # Base input (across all scenarios)
    parser.add_argument(
        "--baseline-data-path",
        dest="baseline_data_path",
        type=str,
        default=config.BASELINE_DATA_PATH,
        help="Path to folder containing both baseline zonedata and -matrices (Given privately by project manager)"),
    # Scenarios' individual input
    parser.add_argument(
        "--emme-paths",
        dest="emme_paths",
        type=str,
        nargs="+",
        required=True,
        help="List of filepaths to .emp EMME-project-files"),
    parser.add_argument(
        "--first-scenario-ids",
        dest="first_scenario_ids",
        type=int,
        nargs="+",
        required=True,
        help="List of first (biking) scenario IDs within EMME project (.emp)."),
    parser.add_argument(
        "--forecast-data-paths",
        dest="forecast_data_paths",
        type=str,
        nargs="+",
        required=True,
        help="List of paths to folder containing forecast zonedata"),
    args = parser.parse_args()

    config.LOG_LEVEL = args.log_level
    config.LOG_FORMAT = args.log_format
    config.SCENARIO_NAME = "input_file_validation"
    log.initialize(config)

    main(args)
