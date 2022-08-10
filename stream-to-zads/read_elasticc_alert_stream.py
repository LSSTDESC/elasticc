import sys
import argparse
import logging
import datetime
from msgconsumer import MsgConsumer

_logger = logging.getLogger(__name__)
if not _logger.hasHandlers():
    _logout = logging.StreamHandler( sys.stderr )
    _logger.addHandler( _logout )
    _formatter = logging.Formatter( f'[msgconsumer - %(asctime)s - %(levelname)s] - %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S' )
    _logout.setFormatter( _formatter )
# _logger.setLevel( logging.INFO )
_logger.setLevel( logging.DEBUG )

def main():
    parser = argparse.ArgumentParser( description="Pull alerts from an elasticc alerts server",
                                      formatter_class=argparse.ArgumentDefaultsHelpFormatter )
    parser.add_argument( "schema", help="File with schema to poll" )
    # parser.add_argument( "-s", "--server", default="public.alerts.ztf.uw.edu:9092",
    #                      help="Kafka server to read from" )
    parser.add_argument( "-s", "--server", default="brahms.lbl.gov:9092",
                         help="Kafka server to read from" )
    parser.add_argument( "--list-topics", action='store_true', default=False, help="Just list topics" )
    parser.add_argument( "-t", "--topic", default=None, help="Topic to poll" )
    parser.add_argument( "-r", "--reset-to-start", default=False, action='store_true',
                         help="Reset topic to start" )
    parser.add_argument( "-b", "--batch-size", type=int, default=100, help="Batch size" )
    parser.add_argument( "-d", "--duration", type=float, default=1., help="Duration in minutes to keep polling " )
    parser.add_argument( "-g", "--groupid", default="rknop-test", help="group.id" )

    args = parser.parse_args()
    
    topics = [ args.topic ] if args.topic is not None else None
        
    consumer = MsgConsumer( args.server, args.groupid, topics, args.schema,
                            consume_nmsgs=args.batch_size, logger=_logger )
    if args.list_topics:
        consumer.print_topics()
        return

    if topics is None:
        _logger.warning( "No topics, exiting." )
        return
    
    if args.reset_to_start:
        for topic in topics:
            consumer.reset_to_start( topic )

    runtime = datetime.timedelta( minutes=args.duration )
            
    consumer.poll_loop( stopafter=runtime )

# ======================================================================

if __name__ == "__main__":
    main()
