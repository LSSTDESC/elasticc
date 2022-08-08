import sys
import pandas
import json
import gzip
import logging
from tomconnection import TomConnection

class TruthLoader(TomConnection):
    def __init__( self, *args, converters=None, urlend=None, renames=None, sep=',', **kwargs ):
        super().__init__( *args, **kwargs )
        if converters is None or urlend is None:
            raise RuntimeError( "Must give converters and url" )
        self.converters = converters
        self.urlend = urlend
        self.renames = renames
        self.sep = sep
        self.cache = []
        self.tot_n_loaded = 0
        self.tot_missing = 0
        self.cache_size = 1000

    def load_csv( self, filename ):
        self.logger.info( f"****** Reading {filename} ******" )
        if ( len(filename) >= 3 ) and ( filename[-3:] == ".gz" ):
            ifp = gzip.open( filename )
        else:
            ifp = open( filename )
        df = pandas.read_csv( ifp, skipinitialspace=True, comment='#', skip_blank_lines=True, sep=self.sep,
                              converters=self.converters )
        ifp.close()
        if self.renames is not None:
            df.rename( self.renames, axis=1, inplace=True )
        # import pdb; pdb.set_trace()
        for i, row in df.iterrows():
            self.cache.append( dict(row) )
            if len( self.cache ) >= self.cache_size:
                self.flush_cache()
        self.flush_cache()

    def flush_cache( self ):
        if len( self.cache ) > 0:
            self.logger.debug( f"Posting {sys.getsizeof(json.dumps(self.cache))/1024:.2f} kiB "
                               f"for {len(self.cache)} truth values" )
            # Keep resending until we get a good result.  The code on the server
            #  should be smart enough to not load duplicates, so we should be
            #  safe just resending.
            ok = False
            while not ok:
                resp = self.rqs.post( f'{self.urlbase}/{self.urlend}', json=self.cache )
                if resp.status_code != 200:
                    self.logger.error( f"ERROR : got status code {resp.status_code}; retrying after 1s..." )
                    time.sleep(1)
                else:
                    ok = True
            rjson = json.loads( resp.text )
            if rjson['status'] != 'ok':
                outlines = [ f"ERROR: got status {rjson['status']}" ]
                for key, val in rjson.items():
                    if key != 'status':
                        outlines.append( f"  {key} : {val}\n" )
                self.logger.error( "\n".join( outlines ) )
            else:
                if 'missing' in rjson:
                    if len( rjson['missing'] ) > 0:
                        self.logger.warning( f'Server told us the following was missing: '
                                             f'{" ".join( [ str(i) for i in rjson["missing"] ] )}' )
                        self.tot_missing += len( rjson['missing'] )
                self.tot_n_loaded += len( rjson["message"] )
                self.logger.info( f'Loaded {len(rjson["message"])} truth values, '
                                  f'cumulative {self.tot_n_loaded} (with {self.tot_missing} missing)\n' )
            self.cache = []
