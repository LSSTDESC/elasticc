import gzip
import logging
import sqlite3
import pickle

import numpy as np
import pandas as pd
from scipy import stats

from ligo.skymap.io import read_sky_map
from ligo.skymap.postprocess import crossmatch

common_snana_keys = [
    'SIM_AV',
    'SIM_DEC',
    'SIM_DLMU',
    'SIM_EXPOSURE_g',
    'SIM_EXPOSURE_i',
    'SIM_EXPOSURE_r',
    'SIM_HOSTLIB_GALID',
    'SIM_LENSDMU',
    'SIM_LIBID',
    'SIM_MAGSMEAR_COH',
    'SIM_MODEL_INDEX',
    'SIM_MODEL_NAME',
    'SIM_MWEBV',
    'SIM_NGEN_LIBID',
    'SIM_NOBS_UNDEFINED',
    'SIM_PEAKMAG_g',
    'SIM_PEAKMAG_i',
    'SIM_PEAKMAG_r',
    'SIM_PEAKMJD',
    'SIM_RA',
    'SIM_REDSHIFT_CMB',
    'SIM_REDSHIFT_FLAG',
    'SIM_REDSHIFT_HELIO',
    'SIM_REDSHIFT_HOST',
    'SIM_RV',
    'SIM_SEARCHEFF_MASK',
    'SIM_SUBSAMPLE_INDEX',
    'SIM_TEMPLATE_INDEX',
    'SIM_TYPE_INDEX',
    'SIM_TYPE_NAME',
    'SIM_VPEC',
    'delta_t_g',
    'delta_t_i',
    'delta_t_r',
    'fluxcal_g',
    'fluxcal_i',
    'fluxcal_r',
    'fluxcalerr_g',
    'fluxcalerr_i',
    'fluxcalerr_r',
    'host_photoz',
    'host_specz',
    'libid',
    'mag_g',
    'mag_i',
    'mag_r',
    'magerr_g',
    'magerr_i',
    'magerr_r',
    'magobs_g',
    'magobs_i',
    'magobs_r',
    'median_delta_t_g',
    'median_delta_t_i',
    'median_delta_t_r',
    'mjd_g',
    'mjd_i',
    'mjd_r',
    'photflag_g',
    'photflag_i',
    'photflag_r',
    'photprob_g',
    'photprob_i',
    'photprob_r',
    'pkmag_g',
    'pkmag_i',
    'pkmag_r',
    'pkmjd',
    'psf_sig1_g',
    'psf_sig1_i',
    'psf_sig1_r',
    'sky_sig_g',
    'sky_sig_i',
    'sky_sig_r',
    'snid',
    'snr_g',
    'snr_i',
    'snr_r',
    'z',
    'zeropt_g',
    'zeropt_i',
    'zeropt_r'
]
"""Keys that are common to all SNANA simulations"""

def get_sim_coinc_map(db_name):
    """
    Return join of sim_inspiral and coinc_inspiral for a LIGOLW
    sqlite database as a dataframe
    """
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    query = """
    SELECT A.mass1, A.mass2, A.spin1x, A.spin1y, A.spin1z,
    A.distance, A.source, A.inclination, A.simulation_id, B.snr, B.ifos
    FROM sim_inspiral AS A JOIN coinc_inspiral AS B
    WHERE A.simulation_id == B.coinc_event_id;
    """

    data = cur.execute(query).fetchall()
    rows = (
        "mass1,mass2,spin1x,spin1y,spin1z,distance,"
        "source,inclination,simulation_id,snr,ifos".split(",")
    )
    return pd.DataFrame(data=data, columns=rows)


def add_redshift_to_dataframe(sim_coinc_df, **kwargs):
    """
    Add cosmological redshift (z column) based on luminosity distance.
    extra arguments passed to `FlatLambdaCDM`
    """
    from astropy import cosmology, units as u
    kwargs = kwargs or dict(H0=70, Om0=0.3)
    cosmo = cosmology.FlatLambdaCDM(**kwargs)
    redshift = [
        cosmology.z_at_value(cosmo.luminosity_distance, d * u.Mpc)
        for d in sim_coinc_df.distance
    ]
    sim_coinc_df['z'] = redshift
    return sim_coinc_df


def add_snid_to_dataframe(sim_coinc_df, colname='snid', source_prefix='GAL'):
    """Add a SNID column to sim_coinc dataframe"""
    source_id = [int(src.split('GAL')[1]) for src in sim_coinc_df.source]
    sim_coinc_df['snid'] = source_id
    return sim_coinc_df


# implemented from plasticc validation repo
def read_serialized_snana_data(filename):
    """Read data from pickled file to a pandas dataframe"""
    with gzip.open(filename, 'rb') as f:
        data = pickle.load(f)

    X = _to_dataframe(data)
    y = pd.get_dummies(X.type == 0, prefix='SNIa', drop_first=True)
    X = X.drop(columns=['type'])

    return X, y


def create_logger(
        log_file, logger_name='kn_rapid',
        fmt= '%(asctime)s -- %(name)s -- %(levelname)s -- %(message)s'):
    """Get a logger object

    Parameters
    ----------
    log_file : str
        Name of log file
    logger_name : str
        name of the logger
    fmt : str
        format, default "%(asctime)s -- %(name)s -- %(message)s"
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    return logger


# implemented from the plasticc validation repo
def _to_dataframe(data, filters='gri'):
    """Converts from a python dictionary to a pandas dataframe"""
    for idx in data:
        sn = data[idx]
        for filt in filters:
            sn['mjd_%s' % filt] = np.array(sn[filt]['mjd'])
            sn['fluxcal_%s' % filt] = np.array(sn[filt]['fluxcal'])
            sn['fluxcalerr_%s' % filt] = np.array(sn[filt]['fluxcalerr'])

            # photflag
            sn['photflag_%s' % filt] = np.array(sn[filt]['photflag'])
            sn['photprob_%s' % filt] = np.array(sn[filt]['photprob'])
            sn['psf_sig1_%s' % filt] = np.array(sn[filt]['psf_sig1'])
            sn['sky_sig_%s' % filt] = np.array(sn[filt]['sky_sig'])
            sn['zeropt_%s' % filt] = np.array(sn[filt]['zeropt'])
            # make mag
            sn['mag_%s' % filt] = np.array(-2.5*np.log10(np.abs(sn[filt]['fluxcal'])))+27.5
            sn['snr_%s' % filt] = (sn[filt]['fluxcalerr'] / np.abs(sn[filt]['fluxcal']))
            sn['magerr_%s' % filt] = np.array(1.086 * sn['snr_%s' % filt])
            sn['magerr_%s' % filt][sn['magerr_%s' % filt] > 0.5] = 0.5
            # find cadence
            sn['delta_t_%s' % filt] = [j-i for i, j in zip(sn['mjd_%s' % filt][:-1], sn['mjd_%s' % filt][1:])]
            sn['median_delta_t_%s' % filt] = np.array(np.median(sn['delta_t_%s' % filt]))
            sn['magobs_%s' % filt] = np.array(np.median(sn['delta_t_%s' % filt]))
            # Mask to keep only photflag obs
            mask = (sn['magerr_%s' % filt] != 0) & (sn['photflag_%s' % filt] != 0)
            sn['snr_%s' % filt] = sn['snr_%s' % filt][mask]
            sn['mag_%s' % filt] = sn['mag_%s' % filt][mask]
            sn['magerr_%s' % filt] = sn['magerr_%s' % filt][mask]
            sn['fluxcal_%s' % filt] = sn['fluxcal_%s' % filt][mask]
            sn['fluxcalerr_%s' % filt] = sn['fluxcalerr_%s' % filt][mask]
            sn['photflag_%s' % filt] = sn['photflag_%s' % filt][mask]
            sn['mjd_%s' % filt] = sn['mjd_%s' % filt][mask]
            del sn[filt]
        sn.update(sn['header'])
        del sn['header']

    return pd.DataFrame.from_dict(data, orient='index')


def get_ligo_skymap_crossmatch(skymap_filename, *args, **kwargs):
    skymap = read_sky_map(skymap_filename, moc=True)
    return crossmatch(skymap, *args, **kwargs)
