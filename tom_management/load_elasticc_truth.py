raise RuntimeError( "Deprecated.  See elasticc2/management/commands/load_snana_fits.py in desc-tom" )

import sys
import argparse
import logging
from truthloader import TruthLoader

class SourceTruthLoader(TruthLoader):
    def __init__( self, *args, **kwargs ):
        urlend = 'elasticc/addtruth'
        converters = { 'SourceID': int,
                       'SNID': int,
                       'MJD': float,
                       'DETECT': int,
                       'TRUE_GENTYPE': int,
                       'TRUE_GENMAG': float }
        renames = {}
        super().__init__( *args, urlend=urlend, converters=converters, renames=renames, **kwargs )

def main():
    logger = logging.getLogger( "main" )
    logout = logging.StreamHandler( sys.stderr )
    logger.addHandler( logout )
    logout.setFormatter( logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s' ) )
    logger.setLevel( logging.DEBUG )

    parser = argparse.ArgumentParser( "Load truth for already-loaded Elasticc sources" )
    parser.add_argument( "filenames", nargs='+', help="Filenames of truth" )
    parser.add_argument( "-u", "--urlbase", default="https://desc-tom.lbl.gov",
                         help="URL of TOM (no trailing / ; default https://desc-tom.lbl.gov)" )
    parser.add_argument( "-U", "--username", default="root", help="TOM username" )
    parser.add_argument( "-p", "--password", default="password", help="TOM password" )
    args = parser.parse_args()

    loader = SourceTruthLoader( args.urlbase, args.username, args.password, logger=logger )
    for filename in args.filenames:
        loader.load_csv( filename )
    logger.info( "All done" )
    

# ======================================================================

if __name__ == "__main__":
    main()
