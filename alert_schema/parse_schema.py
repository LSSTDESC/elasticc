# A quick-n-dirty script to read a schema to make sure its syntax is OK

import sys
import fastavro
import fastavro.schema

if len(sys.argv) != 2:
    print( "Usage: python parse_schema.py <filename>" )
    sys.exit(1)

schema = fastavro.schema.load_schema( sys.argv[1] )

print( fastavro.schema.to_parsing_canonical_form( schema ) )
