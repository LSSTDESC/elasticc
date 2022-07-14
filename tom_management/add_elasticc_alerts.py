import sys
import io
import time
import argparse
import pathlib
import logging
import requests
import json
import tarfile
import gzip
import fastavro

from tomconnection import TomConnection

class AlertLoader(TomConnection):
    def __init__( self, *args, dryrun=False, **kwargs ):
        super().__init__( *args, **kwargs )
        self.dryrun = dryrun
        self.alertcache = []
        self.tot_alerts_loaded = 0 
        self.tot_missing = 0
        self.tot_objs_loaded = 0
        self.tot_sources_loaded = 0
        self.tot_forced_loaded = 0
        self.alert_cache_size = 1000

        self.schema = fastavro.schema.load_schema( "../alert_schema/elasticc.v0_9.alert.avsc" )
        
    def flush_alert_cache( self ):
        if len( self.alertcache ) > 0:
            self.logger.debug( f"Posting {sys.getsizeof(json.dumps(self.alertcache))/1024/1024:.2f} MiB "
                               f"for {len(self.alertcache)} alerts" )
            if self.dryrun:
                self.logger.warning( f'Not actually posting, this is a dry run.' )
            else:
                # Keep resending until we get a good result.  The code on the server
                #   side should be smart enough to not add alerts more than once.
                ok = False
                while not ok:
                    resp = self.rqs.post( f'{self.urlbase}/elasticc/addelasticcalert', json=self.alertcache )
                    if resp.status_code != 200:
                        self.logger.error( f"ERROR : got status code {resp.status_code}; retrying after 1s..." )
                        time.sleep(1)
                    else:
                        ok = True
                rjson = json.loads( resp.text )
                if rjson['status'] != 'ok':
                    with io.StringIO() as strstr:
                        strstr.write( f"ERROR: got status {rjson['status']}\n" )
                        for key, val in rjson.items():
                            if key != 'status':
                                strstr.write( f"  {key} : {val}\n" )
                        self.logger.error( strstr.getvalue() )
                else:
                    self.tot_objs_loaded += len(rjson["message"]["objects"])
                    self.tot_sources_loaded += len(rjson["message"]["sources"])
                    self.tot_alerts_loaded += len(rjson["message"]["alerts"])
                    self.tot_forced_loaded += len(rjson["message"]["forcedsources"])
                    self.logger.info( f'{len(rjson["message"]["alerts"])} alerts '
                                      f'({self.tot_alerts_loaded}), '
                                      f'{len(rjson["message"]["objects"])} objects '
                                      f'({self.tot_objs_loaded}), '
                                      f'{len(rjson["message"]["sources"])} sources '
                                      f'({self.tot_sources_loaded}), '
                                      f'{len(rjson["message"]["forcedsources"])} forced '
                                      f'({self.tot_forced_loaded})' )
            self.alertcache = []

    # def read_alerts( self, fstream ):
    #     reader = fastavro.schemaless_reader( fstream )
    #     alerts = []
        
    #     for rawalert in reader:
    #         # I *think* that the schema in the database match the avro schema directly,
    #         # and as such the webap is expecting all the fields in the alert.
    #         alerts.append( rawalert )
    #     return alerts
            
    def load_directory( self, direc, top=True ):
        direc = pathlib.Path( direc )
        ndid = 0
        for alertfile in direc.iterdir():
            if ( ndid % 10 == 0 ):
                self.logger.debug( f"Did {ndid} files in {direc}" )
            ndid += 1
            if alertfile.is_dir():
                self.logger.debug( f'Going into subdirectory {alertfile}' )
                alertcache = self.load_directory( alertfile, top=False )
            else:
                if ( len(alertfile.name) > 8 ) and ( alertfile.name[-8:] == ".avro.gz" ):
                    fstream = gzip.open( alertfile, "rb")
                elif ( len(alertfile.name) > 5 ) and ( alertfile.name[-5:] == ".avro" ):
                    fstream = open( alertfile, "rb")
                elif ( ( len(alertfile.name) > 7 ) and ( alertfile.name[-7:] == ".tar.gz" ) or
                       ( len(alertfile.name) > 4 ) and ( alertfile.name[-4:] == ".tar" ) ):
                    self.logger.debug( f'Loading tar file {alertfile}' )
                    self.load_tarfile( alertfile )
                    continue
                else:
                    self.logger.warning( f'Skipping unrecognized file {alertfile.name}' )
                    continue

                alert = fastavro.schemaless_reader( fstream, self.schema )
                fstream.close()
                self.alertcache.append( alert )
                if len(self.alertcache) >= self.alert_cache_size:
                    self.flush_alert_cache( )
        if top:
            self.flush_alert_cache()

    def load_tarfile( self, tarfilename ):
        with tarfile.open( tarfilename, 'r' ) as tar:
            members = tar.getmembers()
            for member in members:
                if ( len(member.name) > 8 ) and ( member.name[-8:] == ".avro.gz" ):
                    fstream = gzip.open( tar.extractfile(member.name), 'rb' )
                elif ( len(member.name) > 5 ) and ( member.name[-5:] == ".avro" ):
                    fstream = tar.extractfile(member.name)
                else:
                    continue

                alert = fastavro.schemaless_reader( fstream, self.schema )
                fstream.close()
                self.alertcache.append( alert )
                if len(self.alertcache) >= self.alert_cache_size:
                    self.flush_alert_cache( )
        self.flush_alert_cache()
                
def main():
    logger = logging.getLogger("main")
    logout = logging.StreamHandler( sys.stderr )
    logger.addHandler( logout )
    logout.setFormatter( logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s' ) )
    logger.setLevel( logging.INFO )

    parser = argparse.ArgumentParser()
    parser.add_argument( "-d", "--directory", default=None, help="Directory of alerts to load" )
    parser.add_argument( "-t", "--tarfile", default=None, help="Tar file of alerts to load" )
    parser.add_argument( "-u", "--urlbase", default="https://desc-tom.lbl.gov",
                         help="URL of TOM (no trailing / ; default https://desc-tom.lbl.gov)" )
    parser.add_argument( "-U", "--username", default="root", help="TOM username" )
    parser.add_argument( "-p", "--password", default="password", help="TOM password" )
    parser.add_argument( "-v", "--verbose", default=False, action="store_true", help="Show debug info" )
    parser.add_argument( "--dry-run", default=False, action="store_true",
                         help="Don't actually post alerts to the db, just read and parse them." )
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel( logging.DEBUG )
    
    if args.urlbase[-1] == '/':
        raise ValueError( "Things will fail in a very mysterious fashion if the URL has a trailing slash." )
    
    if ( args.tarfile is None ) == ( args.directory is None ):
        sys.stderr.write( f"--tarfile = {args.tarfile}\n" ) 
        sys.stderr.write( f"--directory = {args.directory}\n" ) 
        sys.stderr.write( "Must specify one of --directory or --tarfile\n" )
        sys.exit(1)

    loader = AlertLoader( args.urlbase, args.username, args.password, dryrun=args.dry_run, logger=logger )

    if ( args.tarfile is not None ):
        loader.load_tarfile( args.tarfile )
    else:
        loader.load_directory( args.directory )
    
# ======================================================================

if __name__ == "__main__":
    main()
    
