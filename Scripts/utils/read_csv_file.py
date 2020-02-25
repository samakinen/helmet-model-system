import os
import pandas
import numpy


def read_csv_file(data_dir, file_end, zone_numbers=None, squeeze=False):
    file_found = False
    for file_name in os.listdir(data_dir):
        if file_name.endswith(file_end):
            if file_found:
                raise NameError("Multiple {} files found in folder {}".format(file_end, data_dir))
            else:
                path = os.path.join(data_dir, file_name)
                file_found = True
    if not file_found:
        raise NameError("No {} file found in folder {}".format(file_end, data_dir))
    if squeeze:
        header = None
    else:
        header = "infer"
    data = pandas.read_csv(
        path, delim_whitespace=True, squeeze=squeeze, keep_default_na=False,
        na_values="", comment='#', header=header)
    if data.index.is_numeric() and data.index.hasnans:
        raise IndexError("Row with only spaces or tabs in file {}".format(path))
    else:
        for i in data.index:
            try:
                if numpy.isnan(i):
                    raise IndexError("Row with only spaces or tabs in file {}".format(path))
            except TypeError:
                # Text indices are ok and should not raise an exception
                pass
    if zone_numbers is not None:
        if (data.index != zone_numbers).any():
            for i in data.index:
                if int(i) not in zone_numbers:
                    raise IndexError("Zone number {} from file {} not found in network".format(i, path))
            for i in zone_numbers:
                if i not in data.index:
                    raise IndexError("Zone number {} not found in file {}".format(i, path))
    return data