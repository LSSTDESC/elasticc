from argparse import ArgumentParser
from functools import partial
from glob import glob
import json

from astropy import table, cosmology
from gwpy import time
import numpy as np
import pandas as pd
from multiprocessing import Pool

from gwemlightcurves.EjectaFits import DiUj2017
from ligo.em_bright.computeDiskMass import computeCompactness, computeDiskMass

TEMPLATE_INDEX_MODEL_PARAM_MAP =  {
    "B19": {"COSTHETA", "MEJ", "PHI"},
    "K17": {"VK", "LOGXLAN", "LOGMASS"}
}

def get_ejecta_mass(m1, m2, eos="APR4_EPP"):
    """Calculate ejecta mass based on Dietrich & Ujevic (2017)"""
    c_ns_1, m_b_1, _ = computeCompactness(m1, eos)
    c_ns_2, m_b_2, _ = computeCompactness(m2, eos)
    try:
        m_rem = np.zeros(m1.size)
    except AttributeError:
        # treat as scalar
        if m_b_2 == 0.0 or m_b_1 == 0.0:
            # treat as NSBH
            m_rem = 0.0
        else:
            # treat as BNS
            m_rem = DiUj2017.calc_meje(m1, m_b_1, c_ns_1, m2, m_b_2, c_ns_2)
        return m_rem
    else:
        non_zero_rem_idx = np.where((m_b_1 > 0) & (m_b_2 > 0))[0]
        m_rem[non_zero_rem_idx] = DiUj2017.calc_meje(
            m1[non_zero_rem_idx], m_b_1[non_zero_rem_idx],
            c_ns_1[non_zero_rem_idx], m2[non_zero_rem_idx],
            m_b_2[non_zero_rem_idx], c_ns_2[non_zero_rem_idx]
        )
    return m_rem


def get_chirp_mass(mass1, mass2):
    return (mass1 * mass2)**(3./5.) / (mass1 + mass2)**(1./5.)


def get_component_mass(chirp_mass, mass_ratio):
    m_tot = chirp_mass * (1 + mass_ratio) ** 1.2 / mass_ratio ** 0.6
    m1 = m_tot / (1 + mass_ratio)
    m2 = m_tot - m1
    return m1, m2


def find_matching_component_mass(
        mej, maxiter=2000, mchirp_ul=1.6, mchirp_ll=0.87,
        mass_ratio_ul=1.0, mass_ratio_ll=0.5,
        component_mass_ll=1.0, component_mass_ul=2.21,
        tol=0.005, eos='APR4_EPP'):
    for _ in range(maxiter):
        mchirp = np.random.uniform(mchirp_ll, mchirp_ul)
        q = np.random.uniform(mass_ratio_ll, mass_ratio_ul)
        m1, m2 = get_component_mass(mchirp, q)
        if m2 < component_mass_ll or m1 > component_mass_ul:
            continue
        m_rem = get_ejecta_mass(m1, m2, eos=eos)
        if np.isclose(m_rem, mej, atol=tol):
            break
    else:
        print(f"Reached max iterations for Mej: {mej}")
        m1 = m2 = 0.0
    return m1, m2


parser = ArgumentParser(
    "Map Mej to component masses using Dietrich & Ujevic fit.")
input_group = parser.add_mutually_exclusive_group(required=True)
input_group.add_argument("-i", "--input",
    help="SNANA header file in FITS format.", default=None)
input_group.add_argument("-j", "--input-files",
    help="Path to header files and glob pattern. Ex. /full/path/*HEAD*FITS.gz",
    default=None)
parser.add_argument("-o", "--output", required=True,
    help="Output csv file having masses and other properties.")
parser.add_argument("--chirp-mass-ul", default=1.6, type=float,
    help="Chirp mass upper limit.")
parser.add_argument("--chirp-mass-ll", default=0.87, type=float,
    help="Chirp mass lower limit.")
parser.add_argument("--mass-ratio-ul", default=1.0, type=float,
    help="Mass ratio upper limit.")
parser.add_argument("--mass-ratio-ll", default=0.5, type=float,
    help="Mass ratio lower limit.")
parser.add_argument("--component-mass-ll", default=1.0, type=float,
    help="Reject component masses below this limit.")
parser.add_argument("--component-mass-ul", default=2.21, type=float,
    help="Reject component masses above this limit.")
parser.add_argument("--eos-name", default="SLY",
    help="Equation of state used to compute compactness.")
parser.add_argument(
    "--ejecta-mass-threshold", default=0.05, type=float,
    help="Leave out entries with ejecta masses above this value.")
parser.add_argument(
    "--sed-model", choices=TEMPLATE_INDEX_MODEL_PARAM_MAP.keys(),
    help="KN SED model")
parser.add_argument(
    "--sim-index-mapping-file", required=True,
    help="JSON file that maps SIM_TEMPLATE_INDEX to SED parameters")
parser.add_argument(
    "--maxiter", default=2000, type=int,
    help="Maximum iterations when searching finding component mass"
)
parser.add_argument(
    "--tolerance", default=0.005, type=float,
    help="Tolerance to use to find ejecta mass"
)
parser.add_argument(
    "--ligo-gpstime-format", action='store_true',
    help="Add to convert first detection times to LIGOGPS format"
)
parser.add_argument("--pool", default=1, type=int,
                    help="Multiprocessing pool count.")
parser.add_argument("--verbose", action='store_true', default=False)
args = parser.parse_args()

if args.input:
    df = table.Table.read(args.input, format='fits').to_pandas()
elif args.input_files:
    fnames = glob(args.input_files)
    if args.verbose:
        print("Total files selected: ", len(fnames))
    tables = []
    for fname in fnames:
        tables.append(table.Table.read(fname, format='fits').to_pandas())
    df = pd.concat(tables, ignore_index=True)
if args.verbose:
    print("Total entries before cuts: ", len(df))
# remove negative redshifts, if any
df = df.loc[df.REDSHIFT_FINAL > 0.]
# load sim index template mapper, get SED parameters, stack to dataframe
sed_model_parameter_dict = TEMPLATE_INDEX_MODEL_PARAM_MAP[args.sed_model]
with open(args.sim_index_mapping_file) as f:
    sim_template_index_map = json.load(f)
sed_params = df.SIM_TEMPLATE_INDEX.astype(str).apply(sim_template_index_map.get)
df = pd.concat((df, pd.DataFrame(list(sed_params))), axis=1)
# handle log mass for K17
if args.sed_model == 'K17':
    if args.verbose:
        print("Performing LOGMASS -> MEJ for K17 model.")
    df['MEJ'] = 10**df['LOGMASS']
# remove entries above the ejecta mass threshold being considered
df = df.loc[df.MEJ <= args.ejecta_mass_threshold]
if args.verbose:
    print(f"Total number of entries selected: {len(df)}")

# extract ejecta mass values and call solver
mej_vals = df['MEJ'].values
func = partial(
    find_matching_component_mass,
    maxiter=args.maxiter, mchirp_ul=args.chirp_mass_ul,
    mchirp_ll=args.chirp_mass_ll, mass_ratio_ul=args.mass_ratio_ul,
    mass_ratio_ll=args.mass_ratio_ll, component_mass_ll=args.component_mass_ll,
    component_mass_ul=args.component_mass_ul,
    tol=args.tolerance, eos=args.eos_name
)
if args.verbose:
    print(f"Running solver with pool size {args.pool}.")
with Pool(args.pool) as pool:
    r = list(pool.map(func, mej_vals))  # map maintains ordering
if args.verbose:
    print("Finished running solver.")
m1_vals, m2_vals = np.array(r).T
df_out = pd.DataFrame(
    data=np.array(r), columns=('mass1_source', 'mass2_source')
)
# add columns from original dataframe
df_out['ra'] = df.SIM_RA.astype(float).values
df_out['dec'] = df.SIM_DEC.astype(float).values
df_out['redshift'] = df.REDSHIFT_FINAL.astype(float).values
df_out['snid'] = df.SNID.astype(int).values
df_out['mej'] = df['MEJ'].values
df_out['costheta'] = df['COSTHETA'].values if args.sed_model=='B19' \
    else np.random.uniform(-1, 1, len(df)) # random inclination for K17; U[cos(iota)]
# add detector-frame masses
df_out['mass1'] = df_out.mass1_source.values * (1 + df.REDSHIFT_FINAL.values)
df_out['mass2'] = df_out.mass2_source.values * (1 + df.REDSHIFT_FINAL.values)
df_out['chirp_mass'] = get_chirp_mass(df_out.mass1.values, df_out.mass2.values)
df_out['first_detection'] = df.PEAKMJD.values
# convert to LIGOGPSTime format if needed
if args.ligo_gpstime_format:
    df_out['first_detection'] = [
        time.to_gps(t) for t in time.Time(
            df.PEAKMJD,
            format='mjd'
        )
    ]
# add distance based on Planck18
df_out['distance'] = cosmology.Planck18.luminosity_distance(
    df.REDSHIFT_FINAL.values).to('Mpc').value
# throw failed values away; failed instances are hard-coded to zero value
df_out = df_out.loc[df_out.mass1 > 0.]
df_out.to_csv(args.output, index=False, float_format='%.4f')

