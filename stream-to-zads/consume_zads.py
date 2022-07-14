import sys
import os
import io
import datetime
import logging
import pathlib
import pandas
import fastavro
import confluent_kafka

from msgconsumer import MsgConsumer

_logger = logging.getLogger(__name__)
_logout = logging.StreamHandler( sys.stderr )
_logger.addHandler( _logout )
_formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S' )
_logout.setFormatter( _formatter )
_logger.setLevel( logging.DEBUG )


def _do_nothing( *args, **kwargs ):
    pass

class ElasticcAlertConsumer:
    def __init__( self, server="brahms.lbl.gov:9092", groupid="rob_elasticc-test-1",
                  topic="elasticc-test-only-1", schema=None, timeout=5, nmsgs=100,
                  polltime=datetime.timedelta(hours=1), reset=False, logger=_logger ):
        self.logger = logger
        if schema is None:
            schema = ( pathlib.Path( os.getenv("HOME") ) /
                       "desc/elasticc/alert_schema/elasticc.v0_9.alert.avsc" )
        self.consumer = MsgConsumer( server, groupid, topic, schema, consume_nmsgs=nmsgs,
                                     consume_timeout=timeout, logger=self.logger )
        self.consumer.print_topics()

        if reset:
            for topic in self.consumer.topics:
                self.logger.debug( f'Resetting {topic}' )
                self.consumer.reset_to_start( topic )

        self.polltime = polltime

        self.totnmsgs = 0
        self.lastmerge = 0
        self.alertids = []
        self.alertsources = []
        self.alertobjects = []
        self.alerttab = None
        
    def handle_messages( self, msgs, merge_every=400 ):
        for msg in msgs:
            alert = fastavro.schemaless_reader( io.BytesIO( msg.value() ), self.consumer.schema )
            self.totnmsgs += 1
            self.alertids.append( alert['alertId'] )
            self.alertsources.append( alert['diaSource']['diaSourceId'] )
            self.alertobjects.append( alert['diaObject']['diaObjectId'] )

        if self.totnmsgs >= ( self.lastmerge + merge_every ):
            self.logger.info( f'Ingested {self.totnmsgs} so far.' )
            self.merge()
            self.lastmerge = self.totnmsgs

    def merge( self ):
        if len(self.alertids) == 0:
            return
        
        tmptab = pandas.DataFrame( { 'alertId': self.alertids,
                                     'diaSourceId': self.alertsources,
                                     'diaObjectId': self.alertobjects } )
        if self.alerttab is None:
            self.alerttab = tmptab
        else:
            self.alerttab = pandas.concat( [ self.alerttab, tmptab ] )
        self.alertids = []
        self.alertsources = []
        self.alertobjects = []
                    
    def __call__( self ):
        self.consumer.poll_loop( handler=lambda msgs: self.handle_messages( msgs, merge_every=100 ),
                                 stopafter=self.polltime )
        self.merge()
        self.consumer.close()
            
def main():
    server = 'public.alerts.ztf.uw.edu:9092'
    topic = 'elasticc-test-mid-july'
    # server = 'brahms.lbl.gov:9092'
    # topic = 'elasticc-test-mid-july'
    
    eac = ElasticcAlertConsumer( polltime=datetime.timedelta(seconds=30), reset=True, logger=_logger,
                                 server=server, topic=topic )
    _logger.info( "Starting poll loop" )
    eac()
    import pdb; pdb.set_trace()

# ======================================================================

if __name__ == "__main__":
    main()
