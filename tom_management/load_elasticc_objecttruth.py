import sys
import argparse
import logging
from truthloader import TruthLoader

class ObjectTruthLoader(TruthLoader):
    def __init__( self, *args, **kwargs ):
        urlend = 'elasticc/addobjecttruth'
        toint = lambda s: int(s) if s!='' else None
        tofloat = lambda s: float(s) if s!='' else None
        converters = { 'SNID': toint,
                       'CID': toint,
                       'LIBID': toint,
                       'SIM_SEARCHEFF_MASK': toint,
                       'GENTYPE': toint,
                       'NON1A_INDEX': toint,
                       'SIM_TEMPLATE_INDEX': toint,
                       'ZCMB': tofloat,
                       'ZHELIO': tofloat,
                       'ZCMB_SMEAR': tofloat,
                       'RA': tofloat,
                       'DEC': tofloat,
                       'MWEBV': tofloat,
                       'GALNMATCH': toint,
                       'GALID': toint,
                       'GALZPHOT': tofloat,
                       'GALZPHOTERR': tofloat,
                       'GALSNSEP': tofloat,
                       'GALSNDDLR': tofloat,
                       'RV': tofloat,
                       'AV': tofloat,
                       'MU': tofloat,
                       'LENSDMU': tofloat,
                       'PEAKMJD': tofloat,
                       'MJD_DETECT_FIRST': tofloat,
                       'MJD_DETECT_LAST': tofloat,
                       'DTSEASON_PEAK': tofloat,
                       'PEAKMAG_u': tofloat,
                       'PEAKMAG_g': tofloat,
                       'PEAKMAG_r': tofloat,
                       'PEAKMAG_i': tofloat,
                       'PEAKMAG_z': tofloat,
                       'PEAKMAG_Y': tofloat,
                       'SNRMAX': tofloat,
                       'SNRMAX2': tofloat,
                       'SNRMAX3': tofloat,
                       'NOBS': toint,
                       'NOBS_SATURATE': toint }
        renames = { 'SNID': "diaObjectId",
                    'CID': "diaObjectId",
                    'LIBID': 'libid',
                    'SIM_SEARCHEFF_MASK': 'sim_searcheff_mask',
                    'GENTYPE': 'gentype',
                    "NON1A_INDEX": 'sim_template_index',
                    'SIM_TEMPLATE_INDEX': 'sim_template_index',
                    'ZCMB': 'zcmb',
                    'ZHELIO': 'zhelio',
                    'ZCMB_SMEAR': 'zcmb_smear',
                    'RA': 'ra',
                    'DEC': 'dec',
                    'MWEBV': 'mwebv',
                    'GALNMATCH': 'galnmatch',
                    'GALID': 'galid',
                    'GALZPHOT': 'galzphot',
                    'GALZPHOTERR': 'galzphoterr',
                    'GALSNSEP': 'galsnsep',
                    'GALSNDDLR': 'galsnddlr',
                    'RV': 'rv',
                    'AV': 'av',
                    'MU': 'mu',
                    'LENSDMU': 'lensdmu',
                    'PEAKMJD': 'peakmjd',
                    'MJD_DETECT_FIRST': 'mjd_detect_first',
                    'MJD_DETECT_LAST': 'mjd_detect_last',
                    'DTSEASON_PEAK': 'dtseason_peak',
                    'PEAKMAG_u': 'peakmag_u',
                    'PEAKMAG_g': 'peakmag_g',
                    'PEAKMAG_r': 'peakmag_r',
                    'PEAKMAG_i': 'peakmag_i',
                    'PEAKMAG_z': 'peakmag_z',
                    'PEAKMAG_Y': 'peakmag_Y',
                    'SNRMAX': 'snrmax',
                    'SNRMAX2': 'snrmax2',
                    'SNRMAX3': 'snrmax3',
                    'NOBS': 'nobs',
                    'NOBS_SATURATE': 'nobs_saturate' }
        super().__init__( *args, urlend=urlend, converters=converters, renames=renames, sep=',', **kwargs )

def main():
    logger = logging.getLogger( "main" )
    logout = logging.StreamHandler( sys.stderr )
    logger.addHandler( logout )
    logout.setFormatter( logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s' ) )
    logger.setLevel( logging.DEBUG )

    parser = argparse.ArgumentParser( "Load object truth for already-loaded Elasticc objects" )
    parser.add_argument( "filenames", nargs='+', help="Filenames of object truth" )
    parser.add_argument( "-u", "--urlbase", default="https://desc-tom.lbl.gov",
                         help="URL of TOM (no trailing / ; default https://desc-tom.lbl.gov)" )
    parser.add_argument( "-U", "--username", default="root", help="TOM username" )
    parser.add_argument( "-p", "--password", default="password", help="TOM password" )
    args = parser.parse_args()

    loader = ObjectTruthLoader( args.urlbase, args.username, args.password, logger=logger )
    for filename in args.filenames:
        loader.load_csv( filename )
    logger.info( "All done" )
    

# ======================================================================

if __name__ == "__main__":
    main()
