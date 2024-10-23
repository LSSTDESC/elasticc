import sys
import logging
import pathlib

import polars

from read_snana import elasticc2_snana_reader


def main():
    esr = elasticc2_snana_reader()
    esr.logger.setLevel( logging.DEBUG )
    outdir = pathlib.Path( "/data/raknop/ELASTICC2_parquet" )

    for objclass in [ 'AGN', 'CART', 'Cepheid', 'EB', 'ILOT', 'KN_B19', 'KN_K17',
                      'Mdwarf-flare', 'PISN-MOSFIT', 'PISN-STELLA_HECORE',
                      'PISN-STELLA_HYDROGENIC', 'RRL', 'SL-SN1a', 'SL-SNII', 'SL-SNIb',
                      'SL-SNIc', 'SLSN-I+host', 'SLSN-I_no_host', 'SNII+HostXT_V19',
                      'SNII-NMF', 'SNII-Templates', 'SNIIb+HostXT_V19', 'SNIIn+HostXT_V19',
                      'SNIIn-MOSFIT', 'SNIa-91bg', 'SNIa-SALT3', 'SNIax', 'SNIb+HostXT_V19',
                      'SNIb-Templates', 'SNIc+HostXT_V19', 'SNIc-Templates',
                      'SNIcBL+HostXT_V19', 'TDE', 'd-Sct', 'dwarf-nova', 'uLens-Binary',
                      'uLens-Single-GenLens', 'uLens-Single_PyLIMA' ]:
    # for objclass in [ 'KN_K17' ]:
        ltcvs = esr.get_all_ltcvs( objclass, agg=True, include_header=True )
        ltcvs.write_parquet( outdir / f'{objclass}.parquet' )
        sys.stderr.write( f"Did {objclass}\n" )

# ======================================================================
if __name__ == "__main__":
    main()
