import sys
import io
import time
import datetime
import atexit
import json
import collections
import logging
import fastavro
import confluent_kafka

_logger = logging.getLogger(__name__)
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[msgconsumer - %(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
# _logger.setLevel( logging.INFO )
_logger.setLevel( logging.DEBUG )

def _do_nothing( *args, **kwargs ):
    pass

class DateTimeEncoder( json.JSONEncoder ):
    def default( self, obj ):
        if isinstance( obj, datetime.datetime ):
            return str( obj.isoformat() )
        else:
            # Should I use super() here?
            return json.JSONEncoder.default( self, obj )
            

class MsgConsumer(object):
    def __init__( self, server, groupid, topics, schema,
                  extraconsumerconfig=None,
                  consume_nmsgs=10, consume_timeout=1, nomsg_sleeptime=1,
                  logger=_logger ):
        self.logger = logger
        self.tot_handled = 0
        if topics is None:
            self.topics = []
        elif isinstance( topics, str ):
            self.topics = [ topics ]
        elif isinstance( topics, collections.abc.Sequence ):
            self.topics = list( topics )
        else:
            raise ValueError( f'topics must be either a string or a list' )
        self.schema = fastavro.schema.load_schema( schema )
        self.consume_nmsgs = consume_nmsgs
        self.consume_timeout = consume_timeout
        self.nomsg_sleeptime = nomsg_sleeptime
        
        consumerconfig = { "bootstrap.servers": server,
                           "auto.offset.reset": "earliest",
                           "group.id": groupid }
        if extraconsumerconfig is not None:
            consumerconfig.update( extraconsumerconfig )
        self.logger.debug( f'Initializing Kafka consumer with\n{json.dumps(consumerconfig, indent=4)}' )
        self.consumer = confluent_kafka.Consumer( consumerconfig )
        atexit.register( self.__del__ )
        
        self.subscribed = False
        self.subscribe( self.topics )

    def close( self ):
        if self.consumer is not None:
            self.consumer.close()
            self.consumer = None
        
    def __del__( self ):
        self.close()

    def subscribe( self, topics ):
        if topics is not None and len(topics) > 0:
            self.consumer.subscribe( topics, on_assign=self._sub_callback )
        else:
            self.logger.warning( f'No topics given, not subscribing.' )

    def reset_to_start( self, topic ):
        self.logger.info( f'Resetting partitions for topic {topic}\n' )
        # Poll once to make sure things are connected
        msg = self.consume_one_message( timeout=4, handler=_do_nothing )
        self.logger.debug( "got throwaway message" if msg is not None else "did't get throwaway message" )
        # Now do the reset
        partitions = self.consumer.list_topics( topic ).topics[topic].partitions
        # partitions is a kmap
        partlist = []
        # for partid, partinfo in partitions.items():
        #     self.logger.info( f'...resetting {partid} ( {partinfo} )' )
        #     # Is this next one redundant?  partinfo should already have the right stuff!
        #     curpart = confluent_kafka.TopicPartition( topic, partinfo.id )
        for i in range(len(partitions)):
            self.logger.info( f'...resetting partition {i}' )
            curpart = confluent_kafka.TopicPartition( topic, i )
            lowmark, highmark = self.consumer.get_watermark_offsets( curpart )
            self.logger.debug( f'Partition {curpart.topic} has id {curpart.partition} '
                               f'and current offset {curpart.offset}; lowmark={lowmark} '
                               f'and highmark={highmark}' )
            curpart.offset = lowmark
            # curpart.offset = confluent_kafka.OFFSET_BEGINNING
            if lowmark < highmark:
                self.consumer.seek( curpart )
            partlist.append( curpart )
        self.logger.info( f'Committing partition offsets.' )
        self.consumer.commit( offsets=partlist, asynchronous=False )
            
    def print_topics( self ):
        cluster_meta = self.consumer.list_topics()
        topics = [ n for n in cluster_meta.topics ]
        topics.sort()
        topicstxt = '\n  '.join(topics)
        self.logger.info( f"\nTopics:\n   {topicstxt}" )

    def _get_positions( self, partitions ):
        return self.consumer.position( partitions )
        
    def _dump_assignments( self, ofp, partitions ):
        ofp.write( f'{"Topic":<32s} {"partition":>9s} {"offset":>12s}\n' )
        for par in partitions:
            ofp.write( f"{par.topic:32s} {par.partition:9d} {par.offset:12d}\n" )
        ofp.write( "\n" )
        
    def print_assignments( self ):
        asmgt = self._get_positions( self.consumer.assignment() )
        ofp = io.StringIO()
        ofp.write( "Current partition assignments\n" )
        self._dump_assignments( ofp, asmgt )
        self.logger.info( ofp.getvalue() )
        ofp.close()
        
    def _sub_callback( self, consumer, partitions ):
        self.subscribed = True
        ofp = io.StringIO()
        ofp.write( "Consumer subscribed.  Assigned partitions:\n" )
        self._dump_assignments( ofp, self._get_positions( partitions ) )
        self.logger.info( ofp.getvalue() )
        ofp.close()

    def poll_loop( self, handler=None, timeout=None, stopafter=datetime.timedelta(hours=1) ):
        """Calls handler with batches of messages."""
        if timeout is None:
            timeout = self.consume_timeout
        t0 = datetime.datetime.now()
        done = False
        while not done:
            self.logger.info( f"Trying to consume {self.consume_nmsgs} messages "
                              f"with timeout {timeout} sec...\n" )
            msgs = self.consumer.consume( self.consume_nmsgs, timeout=timeout )
            if len(msgs) == 0:
                self.logger.info( f"No messages, sleeping {self.nomsg_sleeptime} sec" )
                time.sleep( self.nomsg_sleeptime )
            else:
                if handler is not None:
                    handler( msgs )
                else:
                    self.default_handle_message_batch( msgs )
            if ( datetime.datetime.now() - t0 ) >= stopafter:
                self.logger.info( f"Ending poll loop." )
                done = True

    def consume_one_message( self, timeout=None, handler=None ):
        """Both calls handler and returns a batch of 1 message."""
        if timeout is None:
            timeout = self.consume_timeout
        self.logger.info( f"Trying to consume one message with timeout {timeout} sec...\n" )
        # msgs = self.consumer.consume( 1, timeout=self.consume_timeout )
        msg = self.consumer.poll( timeout )
        if msg is not None:
            if handler is not None:
                handler( [ msg ] )
            else:
                self.default_handle_message_batch( [ msg ] )
        return msg
                
    def default_handle_message_batch( self, msgs ):
        self.logger.info( f'Handling {len(msgs)} messages' )
        timestamp_name = { confluent_kafka.TIMESTAMP_NOT_AVAILABLE: "TIMESTAMP_NOT_AVAILABLE",
                           confluent_kafka.TIMESTAMP_CREATE_TIME: "TIMESTAMP_CREATE_TIME",
                           confluent_kafka.TIMESTAMP_LOG_APPEND_TIME: "TIMESTAMP_LOG_APPEND_TIME" }
        for msg in msgs:
            ofp = io.StringIO()
            ofp.write( f"{msg.topic()} {msg.partition()} {msg.offset()} {msg.key()}\n" )
            if msg.headers() is not None:
                ofp.write( "HEADERS:\n" )
                for key, value in msg.headers():
                    ofp.write( f"  {key} : {value}\n" )
            timestamp = msg.timestamp()
            ofp.write( f"Timestamp: {timestamp[1]} (type {timestamp_name[timestamp[0]]})\n" )
            ofp.write( "MESSAGE PAYLOAD:\n" )
            alert = fastavro.schemaless_reader( io.BytesIO(msg.value()), self.schema )
            # # They are datetime -- Convert to numbers
            # alert['elasticcPublishTimestamp'] = alert['elasticcPublishTimestamp'].timestamp()
            # alert['brokerIngestTimestamp'] = alert['brokerIngestTimestamp'].timestamp()
            ofp.write( json.dumps( alert, indent=4, sort_keys=True, cls=DateTimeEncoder ) )
            ofp.write( "\n" )
            self.logger.info( ofp.getvalue() )
            ofp.close()
        self.tot_handled += len(msgs)
        self.logger.info( f'Have handled {self.tot_handled} messages so far' )
        self.print_assignments()

