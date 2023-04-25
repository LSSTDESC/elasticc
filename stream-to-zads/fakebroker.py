import sys
import io
import math
import pathlib
import logging
import argparse
import datetime
import random
import confluent_kafka
import fastavro

from msgconsumer import MsgConsumer

_rundir = pathlib.Path( __file__ ).parent

_logger = logging.getLogger( __name__ )
_logger.propagate = False
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
_logger.setLevel( logging.INFO )

# ======================================================================

class Classifier:
    def __init__( self, brokername, brokerversion, classifiername, classifierparams,
                  kafkaserver="brahms.lbl.gov:9092", topic="somebody-didnt-replace-a-default",
                  alertschema=None, brokermessageschema=None ):
        self.brokername = brokername
        self.brokerversion = brokerversion
        self.classifiername = classifiername
        self.classifierparams = classifierparams
        self.kafkaserver = kafkaserver
        self.topic = topic
        self.alertschema = alertschema
        self.brokermessageschema = brokermessageschema

        self.nclassified = 0
        self.logevery = 10
        self.nextlog = self.logevery
        
    def determine_types_and_probabilities( self, alert ):
        """Given an alert (a dict in the format of the elasticc alert schema), return a list of 
        two-element tuples that is (classId, probability)."""
        raise RuntimeError( "Need to implement this function in a subclass!" )

    def classify_alerts( self, messages ):
        producer = confluent_kafka.Producer( { 'bootstrap.servers': self.kafkaserver,
                                               'batch.size': 131072,
                                               'linger.ms': 50 } )
        for msg in messages:
            alert = fastavro.schemaless_reader( io.BytesIO(msg.value()), self.alertschema )
            probs = self.determine_types_and_probabilities( alert )
            brokermsg = { "alertId": alert["alertId"],
                          "diaSourceId": alert["diaSource"]["diaSourceId"],
                          "elasticcPublishTimestamp": msg.timestamp()[1],
                          "brokerIngestTimestamp": datetime.datetime.now(),
                          "brokerName": self.brokername,
                          "brokerVersion": self.brokerversion,
                          "classifierName": self.classifiername,
                          "classifierParams": self.classifierparams,
                          "classifications": []
                         }
            for prob in probs:
                brokermsg['classifications'].append( { "classId": prob[0],
                                                       "probability": prob[1] } )
            outdata = io.BytesIO()
            fastavro.write.schemaless_writer( outdata, self.brokermessageschema, brokermsg )
            producer.produce( self.topic, outdata.getvalue() )
        producer.flush()

        self.nclassified += len(messages)
        if ( self.nclassified > self.nextlog ):
            _logger.info( f"{self.classifiername} has classified {self.nclassified} alerts" )
            self.nextlog = self.logevery * ( math.floor( self.nclassified / self.logevery ) + 1 )
            
# ======================================================================

class NugentClassifier(Classifier):
    def __init__( self, *args, **kwargs ):
        super().__init__( "FakeBroker", "v1.0", "NugentClassifier", "100%", **kwargs )

    def determine_types_and_probabilities( self, alert ):
        return [ ( 111, 1.0 ) ]

# ======================================================================

class RandomSNType(Classifier):
    def __init__( self, *args, **kwargs ):
        super().__init__( "FakeBroker", "v1.0", "RandomSNType", "Perfect", **kwargs )
        random.seed()
        
    def determine_types_and_probabilities( self, alert ):
        totprob = 0.
        types = [ 111, 112, 113, 114, 115, 135 ]
        retval = []
        for sntype in types:
            thisprob = random.random() * ( 1 - totprob )
            totprob += thisprob
            retval.append( ( sntype, thisprob ) )
        # SLSN seems to be the default type....
        retval.append( ( 131, 1-totprob ) )
        return retval
        
# ======================================================================        

def main():
    parser = argparse.ArgumentParser( description="Pretend to be an elasticc broker",
                                      formatter_class=argparse.ArgumentDefaultsHelpFormatter )
    parser.add_argument( "--source", default="brahms.lbl.gov:9092",
                         help="Server to pull ELAsTiCC alerts from" )
    parser.add_argument( "-t", "--source-topic", required=True, help="Topic on source server" )
    parser.add_argument( "-g", "--group-id", default="rknop-test",
                         help="Group ID to use on source server" )
    parser.add_argument( "-r", "--reset", action='store_true', default=False,
                         help="Reset to beginning of source stream?" )
    parser.add_argument( "--dest", default="brahms.lbl.gov:9092",
                         help="Server to push broker message alerts to" )
    parser.add_argument( "-u", "--dest-topic", required=True, help="Topic on dest server" )
    parser.add_argument( "-s", "--alert-schema", default=f"{_rundir.parent}/alert_schema/elasticc.v0_9_1.alert.avsc",
                         help="File with elasticc alert schema" )
    parser.add_argument( "-b", "--brokermessage-schema",
                         default=f"{_rundir.parent}/alert_schema/elasticc.v0_9_1.brokerClassification.avsc",
                         help="File with broker message alert schema" )
    
    args = parser.parse_args()

    alertschema = fastavro.schema.load_schema( args.alert_schema )
    brokermsgschema = fastavro.schema.load_schema( args.brokermessage_schema )
    classifiers = [ NugentClassifier( kafkaserver=args.dest, topic=args.dest_topic,
                                      alertschema=alertschema, brokermessageschema=brokermsgschema ),
                    RandomSNType(  kafkaserver=args.dest, topic=args.dest_topic,
                                   alertschema=alertschema, brokermessageschema=brokermsgschema )
                   ]
    
    consumer = MsgConsumer( args.source, args.group_id, args.source_topic, args.alert_schema, logger=_logger,
                            consume_nmsgs=100 )
    if args.reset:
        consumer.reset_to_start( args.source_topic )

    def handle_message_batch( msgs ):
        for cfer in classifiers:
            cfer.classify_alerts( msgs )
        
    consumer.poll_loop( handler = handle_message_batch )
    
# ======================================================================

if __name__ == "__main__":
    main()
