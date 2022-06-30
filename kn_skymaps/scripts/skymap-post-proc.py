from argparse import ArgumentParser
from glob import glob
import os
import sqlite3

from astropy.io import fits
from astropy.table import Table
import pandas as pd


parser = ArgumentParser(
    "Rename skymaps based on MJD-OBS fits card.")
parser.add_argument("-i", "--snana-header-files",
                    help="SNANA B19/K17 header files. Full path + glob pattern.",
                    required=True)
parser.add_argument("-j", "--skymap-fits-files",
                    help="Skymap fits files. Full path + glob pattern.",
                    required=True)
parser.add_argument("-s", "--sqlite-file",
                    help="SQLite file storing the sim_inspiral/coinc_inspiral tables.")
parser.add_argument("-o", "--output-dir", required=True,
                    help="To store renamed fits files")
parser.add_argument("-v", "--verbose", action='store_true', default=False,
                    help="Add verbosity")
args = parser.parse_args()
# put all SNANA header files in a dataframe
snana_header_files = glob(args.snana_header_files)
if args.verbose:
    print("Loading all SNANA header files")
_header_files = []
for fname in snana_header_files:
    _header_files.append(Table.read(fname, format='fits').to_pandas())
df_lightcurves = pd.concat(_header_files, ignore_index=True)
# load gw coincidence properties
with sqlite3.connect(args.sqlite_file) as conn:
    df_gw = pd.read_sql("SELECT * FROM sim_inspiral", conn)
# create a SNID column in the GW dataframe and join with SNANA headers
if args.verbose:
    print("Joining GW and SNANA info")
df_gw['SNID'] = df_gw.source.apply(lambda x: x.strip('GAL')).astype(int)
df_lightcurves['SNID'] = df_lightcurves.SNID.astype(int)
df_coinc = df_gw.merge(df_lightcurves, on='SNID')

skymap_filenames = glob(args.skymap_fits_files)
assert len(df_coinc) == len(skymap_filenames), ("Number of simulation_ids "
    "should match number of skymaps")

if args.verbose:
    print(f"Renaming {len(skymap_filenames)} skymap fits files")
for fname in skymap_filenames:
    if args.verbose:
        print(f"Renaming {fname}")
    simulation_id = int(os.path.basename(fname).strip('.fits'))
    snid = df_coinc.loc[df_coinc.simulation_id==simulation_id]['SNID']
    assert len(snid) == 1, "Only one SNID should match"
    snid = snid.values[0]

    hdu = fits.open(fname)
    # Remove content of ORIGIN card since this is not from LVK
    hdu[1].header['ORIGIN'] = ''
    mjd = hdu[1].header['MJD-OBS']
    new_fname = f"SNID_{snid}_MJD_{mjd}.fits"
    new_path = os.path.join(args.output_dir, new_fname)
    hdu.writeto(new_path)

