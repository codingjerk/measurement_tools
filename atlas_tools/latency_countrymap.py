from collections import defaultdict
import argparse
import logging
import os

import folium
import geopandas
import pandas
import pkg_resources

from atlas_tools.measurement import ping_measure
from atlas_tools.util import base_parser, atlas_parser, ping_parser, start_logger, check_ping_args

SHAPEFILE_DIR = 'countries'
SHAPEFILE_NAME = 'ne_50m_admin_0_countries.shp'

logger = logging.getLogger(__name__)


def _handle_data(ping_results):
    states_array = defaultdict(list)
    for (_, _, _, _, region, _, _, rtt) in ping_results:
        states_array[region].append(rtt)

    states = dict()
    for country, rtt_list in states_array.items():
        states[country] = min(int(sum(rtt_list) / len(rtt_list)), 120)

    return states


def _choose_color(feature, dataframe, linear):
    iso = feature['properties']['iso_a2']
    if iso in dataframe.index:
        return linear(dataframe.at[iso, 'Latency'])
    else:
        return 'lightgrey'


def _draw_countrymap(cut_countries, fname):
    logger.info('Drawing the countrymap')

    resource_dir = pkg_resources.resource_filename(__package__, SHAPEFILE_DIR)
    resource_fname = os.path.join(resource_dir, SHAPEFILE_NAME)
    df_shapefile_countries = geopandas.GeoDataFrame.from_file(resource_fname)

    dataframe = pandas.DataFrame(
        data=list(cut_countries.items()),
        columns=['iso_a2', 'Latency'],
    )
    dataframe.set_index('iso_a2', inplace=True)

    linear = folium.LinearColormap(
        ['green', 'yellow', 'red'], vmin=0., vmax=120.
    ).to_step(6)

    countrymap = folium.Map(
        location=[20, 20],
        zoom_start=3, min_zoom=2, max_zoom=8,
        tiles='Stamen Terrain',
    )

    folium.GeoJson(
        df_shapefile_countries,
        style_function=lambda feature: {
            'fillColor': _choose_color(feature, dataframe, linear),
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.6
        },
        highlight_function=lambda feature: {
            'fillColor': _choose_color(feature, dataframe, linear),
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0.7,
            'dashArray': '5, 5'
        }
    ).add_to(countrymap)

    countrymap.add_child(linear)
    countrymap.save(fname)


def create_countrymap(fname, atlas_key, target, country=None,
                      probe_limit=None, timeout=None, measurements_list=None):
    pings = ping_measure(
        atlas_key, target,
        country=country,
        probe_limit=probe_limit,
        timeout=timeout,
        measurements_list=measurements_list
    )

    cut_countries = _handle_data(pings.results)
    _draw_countrymap(cut_countries, fname)


def main():
    parser = argparse.ArgumentParser(
        parents=[base_parser(), atlas_parser(), ping_parser()],
        description='create a world map which shows target latencies (RTT) from different countries'
    )
    parser.add_argument(
        '-f', '--filename',
        help="output HTML filename (default: 'countrymap_<target>.html')"
    )
    args = parser.parse_args()

    check_ping_args(parser, args)
    if args.filename is None:
        args.filename = 'countrymap_%s.html' % args.target

    start_logger('atlas_tools', verbose=args.verbose)

    create_countrymap(
        args.filename, args.key, args.target,
        country=args.country,
        probe_limit=args.probe_number,
        timeout=args.timeout,
        measurements_list=args.msms
    )


if __name__ == '__main__':
    main()