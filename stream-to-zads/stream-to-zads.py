import sys
import os
import re
import io
import time
import requests
import json
import logging
import logging.handlers
import datetime
import dateutil.parser
import pathlib
import tarfile
import gzip
import fastavro
import confluent_kafka

_logger = logging.getLogger(__name__)
_logout = logging.handlers.TimedRotatingFileHandler( "/nightcache/stream-to-zads.log", when='d', interval=1 )
_logger.addHandler( _logout )
_formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S' )
_logout.setFormatter( _formatter )
_logger.setLevel( logging.INFO )
# _logger.setLevel( logging.DEBUG )

class AlertStreamer:
    def __init__( self, alertdirs=None, schemafile=None, kafka_broker='brahms.lbl.gov:9092',
                  kafka_topic='elasticc-test-only-1', compression_factor=10,
                  campaign_start=datetime.datetime(2022,7,6,7,0,0), nights_done_cache="/nightcache/nightsdone.lis",
                  simnight0=60274, simnight1=61378,
                  tom_url='https://desc-tom.lbl.gov', tom_username='rknop', tom_passwdfile='/secrets/tom_passwd',
                  dry_run=False, logger=_logger ):
        self.logger = logger
        
        if alertdirs is None:
            self.alertdirs = [ '/alerts/ELASTICC_ALERTS_TEST_EXTRAGALACTIC-SNIa/ALERTS',
                               '/alerts/ELASTICC_ALERTS_TEST_EXTRAGALACTIC-nonIa/ALERTS',
                               '/alerts/ELASTICC_ALERTS_TEST_GALACTIC/ALERTS' ]
        else:
            self.alertdirs = alertdirs

        if schemafile is None:
            self.schemafile = '/elasticc/alert_schema/elasticc.v0_9.alert.avsc'
        else:
            self.schemafile = schemafile
        self.logger.info( f"Reading schema from {self.schemafile}" )
        self.schema = fastavro.schema.load_schema( self.schemafile )

        self.kafka_broker = kafka_broker
        self.kafka_topic = kafka_topic

        self.logger.info( f"Kafka broker={kafka_broker} ; topic={kafka_topic}" )
        
        self.compression_factor = compression_factor
        self.kafka_batch_size_bytes = 131072
        self.kafka_linger_ms = 50

        self.dry_run = dry_run
        self.t0 = campaign_start
        # Make sure this is a timezone-aware datetime
        if self.t0.tzinfo is None or self.t0.tzinfo.utcoffset(self.t0) is None:
            self.t0 = self.t0.replace( tzinfo=datetime.timezone.utc )

        self.totaln0 = simnight0
        self.totaln1 = simnight1

        self.logger.info( f"AlertStreamer: t0 = {self.t0.isoformat()} ; "
                          f"compression factor = {self.compression_factor} ; "
                          f"dry run = {self.dry_run}" )

        self.nights_done_cache = pathlib.Path( nights_done_cache )
        if self.nights_done_cache.is_file():
            self.logger.info( f"Reading nights done from {self.nights_done_cache}" )
            with open( self.nights_done_cache ) as ifp:
                self.nights_done = [ int(n) for n in ifp.readlines() ]
        else:
            self.logger.warning( f"No nights done cache {self.nights_done_cache}." )
            self.nights_done = []

        self.tom_url = tom_url
        self.tom_username = tom_username
        self.tom_passwdfile = tom_passwdfile
        with open( tom_passwdfile ) as ifp:
            self.tom_passwd = ifp.readline().strip()

    def log_into_tom( self ):
        rqs = requests.session()
        rqs.get( f'{self.tom_url}/accounts/login/' )
        res = rqs.post( f'{self.tom_url}/accounts/login/',
                        data={ "username": self.tom_username,
                               "password": self.tom_passwd,
                               "csrfmiddlewaretoken": rqs.cookies['csrftoken'] } )
        if res.status_code != 200:
            raise RuntimeError( f"Failed to log in; http status: {res.status_code}" )
        if 'Please enter a correct' in res.text:
            raise RuntimeError( "Failed to log in.  I think.  Put in a debug break and look at res.text" )
        rqs.headers.update( { 'X-CSRFToken': rqs.cookies['csrftoken'] } )
        return rqs

    def notify_tom( self, rqs, ids ):
        if len(ids) == 0:
            return
        
        outercountdown = 5
        while outercountdown >= 0:
            countdown = 5
            try:
                while countdown >= 0:
                    try:
                        res = rqs.post( f'{self.tom_url}/elasticc/markalertsent', json=ids )
                        if res.status_code != 200:
                            self.logger.error( f"Got status_code={res.status_code} from TOM" )
                            raise RuntimeError( "Got status_code={res.status_code} from TOM" )
                        data = json.loads( res.text )
                        if ( not 'status' in data ) or ( data['status'] != 'ok' ):
                            strio = io.StringIO( "" )
                            if data['status'] == 'error':
                                strio.write( "Error return from TOM:\n" )
                                strio.write( f"   message: {data['message']}\n" )
                                strio.write( f"   exception: {data['exception']}\n" )
                                strio.write( f"   traceback:\n{data['traceback']}\n" )
                            else:
                                strio.write( f"Unexpected return from TOM: {data}" )
                            self.logger.error( strio.getvalue() )
                            raise RuntimeError( strio.getvalue() )
                        countdown = -1
                    except Exception as e:
                        if countdown >= 0:
                            self.logger.error( "Failed too many times, bailing." )
                            raise e
                        self.logger.error( "Retrying in 1 second..." )
                        time.sleep( 1 )
                        countdown -= 1
                outercountdown = -1
            except Exception as e:
                if outercountdown <= 0:
                    self.logger.error( "Outer tom notification failed too many times, bailing." )
                    raise e
                time.sleep( 1 )
                self.logger.error( "Going to try logging back into the tom." )
                rqs = self.log_into_tom()
                outercountdown -= 1
        return rqs
    
    def stream_todays_batch( self, alert_delay=0, diffmjd_delay=0.2, diffnight_delay=5 ):
        now = datetime.datetime.now( datetime.timezone.utc )
        curday = ( now - self.t0 ).days
        n0 = self.totaln0 + curday * self.compression_factor
        n1 = n0 + self.compression_factor - 1

        if ( n0 < self.totaln0 ): n0 = self.totaln0
        if ( n1 > self.totaln1 ): n1 = self.totaln1

        if ( n0 > self.totaln1 ) or ( n1 < self.totaln0 ):
            self.logger.error( f"Today's range {n0}..{n1} is outside the "
                               f"overall range {self.totaln0}..{self.totaln1}\n" )
            return False

        if self.dry_run:
            self.logger.info( f"DRY RUN: reading and planning to stream alerts from nights {n0} through {n1}." )
        self.logger.info( f"{'Fake-S' if self.dry_run else 'S'}treaming alerts from nights {n0} through {n1}." )
        self.logger.info( f"Will delay {alert_delay}s between alerts, {diffmjd_delay}s between "
                          f"exposures, and {diffnight_delay}s between nights." )
        
        nameparse = re.compile( 'alert_mjd([0-9]+\.[0-9]+)_obj([0-9]+)_src([0-9]+).avro.gz' )

        if not self.dry_run:
            producer = confluent_kafka.Producer( { 'bootstrap.servers': self.kafka_broker,
                                                   'batch.size': self.kafka_batch_size_bytes,
                                                   'linger.ms': self.kafka_linger_ms
                                                  } )
            rqs = self.log_into_tom()
            
        nstreamed = 0
        bytesstreamed = 0

        # Do it one "night" at a time
        for n in range( n0, n1+1 ):
            nightnstreamed = 0
            nightbytesstreamed = 0
            
            if n in self.nights_done:
                self.logger.warning( f"Night {n} already done, not doing it again." )
                continue
            self.logger.info( f"Doing night {n}" )

            # Build the full list of alerts to stream
            # I'm assuming that no filename will be repeated in different
            # tar files.  Since the source ID is embedded in the filename,
            # this should be a good assumption.
            alertfilenames = []
            alerts = {}
            for adir in self.alertdirs:
                self.logger.info( f"Looking in {adir}" )
                tarpath = pathlib.Path( adir ) / f"NITE{n}.tar.gz"
                if not tarpath.is_file():
                    self.logger.error( f"{str(tarpath)} is not a regular file!  Moving on." )
                    continue
                self.logger.info( f"Reading {tarpath.name}..." )
                with tarfile.open( tarpath, "r" ) as tar:
                    members = [ m.name for m in tar.getmembers() if nameparse.search(m.name) ]
                    for alertfile in members:
                        alertfilenames.append( alertfile )
                        if alertfile in alerts:
                            self.logger.warning( f"alert['{alertfilename}'] exists, and shouldn't!" )
                        else:
                            alerts[ alertfile ] = []
                        fstream = gzip.open( tar.extractfile( alertfile ), 'rb' )
                        rawalert = fastavro.schemaless_reader( fstream, self.schema )
                        alerts[ alertfile ].append( rawalert )
                        # reader = fastavro.reader( fstream )
                        # for rawalert in reader:
                        #     alerts[ alertfile ].append( rawalert )
                        fstream.close()
                self.logger.info( f"...done reading {tarpath.name}; up to {len(alertfilenames)} alert files." )

            # Sort by mjd (which is the same as sorting by filename)
            alertfilenames.sort()

            self.logger.info( f"Streaming {len(alertfilenames)} alerts for night {n}" )

            lastmjd = ''
            idsproduced = []
            for alertfile in alertfilenames:
                match = nameparse.search( alertfile )
                if not match:
                    self.logger.error( f"Failed to parse {alertfile}; this should not happen!" )
                    continue
                mjd = match.group(1)
                if mjd != lastmjd:
                    if diffmjd_delay > 0:
                        if not self.dry_run:
                            producer.flush()
                            rqs = self.notify_tom( rqs, idsproduced )
                            idsproduced = []
                        self.logger.debug( f'Starting exposure mjd {mjd}; '
                                           f'have {"fake-" if self.dry_run else " "}streamed '
                                           f'{nightnstreamed} for night {n}; '
                                           f'sleeping {diffmjd_delay} sec' )
                        time.sleep( diffmjd_delay )
                        lastmjd = mjd
                for alert in alerts[ alertfile ]:
                    if ( nightnstreamed % 500 ) == 0:
                        self.logger.info( f'Have {"fake-" if self.dry_run else ""}streamed '
                                          f'{nightnstreamed} for night {n}.' )
                    alertbytes = io.BytesIO()
                    fastavro.write.schemaless_writer( alertbytes, self.schema, alert )
                    if not self.dry_run:
                        producer.produce( self.kafka_topic, alertbytes.getvalue() )
                        idsproduced.append( alert['alertId'] )
                    nightbytesstreamed += len( alertbytes.getvalue() )
                    nightnstreamed += 1
                    if alert_delay > 0:
                        time.sleep( alert_delay )

            producer.flush()
            rqs = self.notify_tom( rqs, idsproduced )
            idsproduced = []
            self.logger.info( f'{"Fake-s" if self.dry_run else "S"}treamed {nightnstreamed} total alerts for night {n} '
                              f'({nightbytesstreamed/1024/1024:.3f} MiB).' )
            nstreamed += nightnstreamed
            bytesstreamed += nightbytesstreamed
            self.nights_done.append( n )
            with open( self.nights_done_cache, "wa" ) as ofp:
                ofp.write( f"{n}\n" )
            time.sleep( diffnight_delay )

        # This next line is gratuitous
        producer.flush()
        rqs = self.notify_tom( rqs, idsproduced )
        idsproduced = []
        self.logger.info( f"Done with today's batch.  {'Fake-s' if self.dry_run else 'S'}treamed {nstreamed} alerts "
                          f"({bytesstreamed/1024/1024:.3f} MiB)." )

# ======================================================================

def main():
    if os.getenv( "ELASTICC_COMPRESSION_FACTOR" ) is not None:
        compression_factor = int( os.getenv( "ELASTICC_COMPRESSION_FACTOR" ) )
    else:
        compression_factor = 10

    if os.getenv( "ELASTICC_START_TIME" ) is not None:
        t0 = dateutil.parser.isoparse( os.getenv( "ELASTICC_START_TIME" ) )
    else:
        t0 = datetime.datetime( 2022, 7, 6, 7, 0 )

    if os.getenv( "ELASTICC_ALERT_SERVER" ) is not None:
        kafka_broker = os.getenv( "ELASTICC_ALERT_SERVER" )
    else:
        kafka_broker = 'brahms.lbl.gov:9092'

    if os.getenv( "ELASTICC_ALERT_TOPIC" ) is not None:
        kafka_topic = os.getenv( "ELASTICC_ALERT_TOPIC" )
    else:
        kafka_topic = 'elasticc-test-only-1'

    if os.getenv( "ELASTICC_DRY_RUN", None ) is not None:
        dry_run = True
    else:
        dry_run = False
        
    streamer = AlertStreamer( compression_factor=compression_factor, campaign_start=t0,
                              kafka_broker=kafka_broker, kafka_topic=kafka_topic, dry_run=dry_run )
    while True:
        streamer.stream_todays_batch()
        _logger.info( f'Sleeping 1 hour' )
        time.sleep( 3600 )

# ======================================================================
if __name__ == "__main__":
    main()
