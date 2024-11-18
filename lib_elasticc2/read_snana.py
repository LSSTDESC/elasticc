import sys
import os
import pathlib
import re
import logging
import warnings

import numpy
import pyarrow
import pandas
import polars

from astropy.io import fits
import astropy.table

# _default_log_level = logging.INFO
_default_log_level = logging.DEBUG

_logger = logging.getLogger( "ELAsTiCC2_SNANAReader" )
_logout = logging.StreamHandler( sys.stderr )
_logger.addHandler( _logout )
_formatter = logging.Formatter( f'[%(asctime)s - %(levelname)s] - %(message)s',
                                datefmt='%Y-%m-%d %H:%M:%S' )
_logout.setFormatter( _formatter )
_logger.propagate = False
_logger.setLevel( _default_log_level )

class elasticc2_snana_reader:
    """A class for reading the ELAsTiCC2 SNANA FITS files in to Pandas data frames."""

    def __init__( self, elasticc2_snana_dir=pathlib.Path( os.getenv('TD', "/global/cfs/cdirs/desc-td") ) / "ELASTICC2",
                  dir_prefix='ELASTICC2_FINAL_', waste_memory_on_heads=False, logger=None ):
        """Create a reader.

        Parameters
        ----------
          elasticc2_sana_dir : str or Path
            The directory where all the SNANA FITS files are found.
            This file should contain nothing but 38 subdirectories, each
            named {dir_prefix}<classname>.  Defaults to $TD/ELASTICC2
            if the TD env var is set, otherwise to
            /global/cfs/cdirs/desc-td/ELASTICC2 (the location on NERSC).

          dir_prefix: str
            What do all the subdirectories (and files within them) start
            with?  This defaults to ELASTICC2_FINAL_, which is right for
            the ELAsTiCC2 test set.  Make it ELASTICC2_TRAIN_02_ for the
            ELAsTiCC2 training set (with, of course, elasticc2_snana_dir
            pointing at directory with the training files.)
        
          waste_memory_on_heads : bool, default False
            If True, whenever you read the HEAD files for a new object,
            it will cache that head file so that next time you need to
            access it, it will be fast.  This can eat up a lot of
            memory; the object types with larger numbers of objects
            (SNIa, SNII, etc.) will use 1-2GB of memory to store the
            head file.  If False, only the last accessed HEAD file data
            is cached.  As long as you're working with a single class at
            a time, this should still be good enough.

        """


        global _logger
        self.logger = logger if logger is not None else _logger

        self.elasticc2_snana_dir = pathlib.Path( elasticc2_snana_dir )
        if not self.elasticc2_snana_dir.is_dir():
            raise RuntimeError( f"Can't open directory {self.elasticc2_snana_dir}" )

        self.dir_prefix=dir_prefix

        self.subdirs = {}
        subdirs = self.elasticc2_snana_dir.glob( f"{self.dir_prefix}*" )
        for subdir in subdirs:
            if pathlib.Path( subdir ).is_dir():
                match = re.search( f"^{self.dir_prefix}(.*)$", subdir.name )
                self.subdirs[ match.group(1) ] = subdir
        self._obj_class_names = list( self.subdirs.keys() )
        self._obj_class_names.sort()
        # We could cache all of the head files in a dictionary,
        #   which would save multiple reads.  But, the SNIa-SALT3
        #   head file is 1.6GB of memory, and a bunch of the others
        #   are big too, so that could easily lead to too much
        #   memory usage.  As such, by default, just cache the
        #   last head file read.  For most usage, that should
        #   provide the speedup we want.
        self.waste_memory_on_heads = waste_memory_on_heads
        if self.waste_memory_on_heads:
            self._heads_cache = {}
        else:
            self._head_cache_class = None
            self._head_cache = None

        self.phots = {}


    @property
    def obj_class_names( self ):
        """A list of all the object class names known."""
        return self._obj_class_names


    # For ELAsTiCC2, PHOTFLAG has the following definitions:
    #
    #   PHOTFLAG_SATURATE:    1024   0x0400
    #   PHOTFLAG_TRIGGER:     2048   0x0800
    #   PHOTFLAG_DETECT:      4096   0x1000

    @property
    def photflag_saturate( self ):
        """Bitwise AND the PHOTFLAG field with this to find saturated points."""
        return 0x0400

    @property
    def photflag_trigger( self ):
        """Bitwise AND the PHOTFLAG field with this to find the first point of each object that triggered dtection."""
        return 0x0800

    @property
    def photflag_detect( self ):
        """Bitwise AND the PHOTFLAG field with this to find detected points.

        (Including all points simulates forced photometry.)

        """
        return 0x1000


    def get_object_truth( self, obj_class_name, return_format='polars' ):
        """Read the object truth table for a given class.

        Note!  Most of the truth information you need is already in the
        head file.  Look at the SIM_* columns.

        Parameters
        ----------
          obj_class_name : str
            The object class name, e.g. "AGN", "SNIa-SALT3".  Must be one
            of the elements of the list self.obj_class_names

          return_format : str, default 'polars'
            One of 'polars' or 'pandas'

        Returns
        -------
          polars DataFrame or pandas DataFrame


        """
        if obj_class_name not in self.subdirs:
            raise ValueError( f"Unknown object class name {obj_class_name}" )
        if return_format not in ('polars', 'pandas'):
            raise ValueError( f"Unknown return_format {return_format}" )

        dumpfile = self.elasticc2_snana_dir / self.subdirs[obj_class_name] / f"{self.dir_prefix}{obj_class_name}.DUMP"
        if not dumpfile.is_file():
            raise FileNotFoundError( f"Can't find truth file {dumpfile}" )
        self.logger.info( f"Reading {dumpfile}" )
        # polars read_csv is not as functional as the pandas version, sadly.
        # pandas just ignores blank lines, which is what we need for the DUMP file.
        pandas_df = pandas.read_csv( dumpfile, sep=r'\s+', header=0, comment='#' )
        pandas_df.drop( 'VARNAMES:', inplace=True, axis=1 )
        # Principle of least surprise: in the HEAD file, the object id is SNID,
        #   whereas it's CID in the truth file.  Rename.
        pandas_df.rename( { 'CID': 'SNID' }, axis='columns', inplace=True )

        if return_format == 'polars':
            return polars.from_pandas( pandas_df )
        else:
            return pandas_df


    def get_head( self, obj_class_name, return_format='polars' ):
        """Read all of the HEAD files for a given object class.

        Parameters
        ----------
          obj_class_name : str
            The object class name, e.g. "AGN", "SNIa-SALT3".  Must be one
            of the elements of the list self.obj_class_names

          return_format : str, default 'polars'
            'polars' or 'pandas'

        Returns
        -------
          Either a polars.DataFrame (if return_format is 'polars')
          or a pandas.DataFrame (if return_format is 'pandas').

          Using return_format='polars' will generally be more efficient
          because polars is the format stored in internal caches.

        """
        if obj_class_name not in self.subdirs:
            raise ValueError( f"Unknown object class name {obj_class_name}" )
        if return_format not in ( 'polars', 'pandas' ):
            raise ValueError( f"Unknown return_format {return_format}" )

        retdf = None

        if self.waste_memory_on_heads:
            if obj_class_name in self._heads_cache.keys():
                retdf = self._heads_cache[ obj_class_name ]
        else:
            if self._head_cache_class == obj_class_name:
                retdf = self._head_cache

        if retdf is None:
            self.logger.info( f"Reading HEAD files from {self.subdirs[obj_class_name]}" )

            headparsere = re.compile( r'^(?P<base>.*)-(?P<num>\d+)_HEAD\.FITS(?P<gz>\.gz)?$' )

            foundheads = {}
            self.phots[ obj_class_name ] = {}
            # First, look for non-gzipped files
            headfiles = self.subdirs[obj_class_name].glob( "*HEAD.FITS" )
            for headfile in headfiles:
                match = headparsere.search( headfile.name )
                if match is None:
                    raise ValueError( f"Error parsing HEAD filename {headfile.name}" )
                foundheads[match.group('num')] = headfile
                self.phots[obj_class_name][match.group('num')] = (
                    headfile.parent / f"{match.group('base')}-{match.group('num')}_PHOT.FITS" )
            # Now, look for gzipped files
            headfiles = self.subdirs[obj_class_name].glob( "*HEAD.FITS.gz" )
            for headfile in headfiles:
                match = headparsere.search( headfile.name )
                if match is None:
                    raise ValueError( f"Error parsing HEAD filename {headfile.name}" )
                if match.group('num') not in foundheads.keys():
                    foundheads[match.group('num')] = headfile
                    self.phots[obj_class_name][match.group('num')] = (
                        headfile.parent / f"{match.group('base')}-{match.group('num')}_PHOT.FITS.gz" )

            # Read all the heads in order
            heads = []
            nums = list( foundheads.keys() )
            nums.sort()
            for num in nums:
                atab = astropy.table.Table.read( foundheads[num] )
                # Convert to polars DataFrame, also byteswapping as necessary.
                # (FITS files are big-endian, and astropy just reads them as such.
                # X86 Linux, at least, is little-endian.)
                dtypes = [ atab[c].dtype if atab[c].dtype.isnative else  atab[c].dtype.name  for c in atab.columns ]
                df = polars.from_dict( { c: polars.Series( atab[c].astype(d) )
                                         for c, d in zip( atab.columns, dtypes ) } )

                # SNID comes in as a b-string, convert it to an int (Polars cast chokes on the spaces)
                df = df.with_columns( polars.col("SNID").cast( str ) )
                df = df.with_columns( polars.col("SNID").str.strip_chars() )
                df = df.with_columns( polars.col("SNID").cast( polars.Int64 ) )

                # Convert all other "Binary" fields to strings, as that's what they really are
                for col in [ c for c in df.columns if df[c].dtype == polars.Binary ]:
                    df = df.with_columns( polars.col(col).cast( str ) )
                    df = df.with_columns( polars.col(col).str.strip_chars() )

                # Drop some columns that don't contain useful information
                #  (Either it's null, or always the same because ELAsTiCC2 is
                #  a catalog-based simulation, not a pixel-based simulation.)
                df.drop_in_place( 'IAUC' )
                df.drop_in_place( 'FAKE' )
                df.drop_in_place( 'PIXSIZE' )
                df.drop_in_place( 'NXPIX' )
                df.drop_in_place( 'NYPIX' )
                df.drop_in_place( 'SEARCH_TYPE' )

                # Add the file_num and head_filename because we'll need that later
                df = df.with_columns( file_num=polars.lit(num), head_filename=polars.lit(foundheads[num].name) )

                heads.append( df )

            retdf = polars.concat( heads )
            if self.waste_memory_on_heads:
                self._heads_cache[ obj_class_name ] = retdf
            else:
                self._head_cache_class = obj_class_name
                self._head_cache = retdf

        if return_format == 'pandas':
            return retdf.to_pandas()
        else:
            return retdf


    def _read_one_phot_file( self, photfile, ptrmin=None, ptrmax=None, return_format='polars' ):
        if ( ptrmin is None ) != ( ptrmax is None ):
            raise RuntimeError( "Pass either both or neither of ptrmin and ptrmax" )
        if return_format not in ('polars', 'pandas'):
            raise ValueError( f"Unknown return_format {return_format}" )

        with fits.open( photfile, memmap=True ) as phothdu:
            if ptrmin is not None:
                photrows = phothdu[1].data[ ptrmin:ptrmax ]
            else:
                photrows = phothdu[1].data

        # Keep only the columns meaningful for ELAsTiCC
        # photrows.keep_columns( ['MJD', 'BAND', 'PHOTFLAG', 'PHOTPROB', 'FLUXCAL', 'FLUXCALERR',
        #                         'PSF_SIG1', 'SKY_SIG', 'RDNOISE', 'ZEROPT', 'ZEROPT_ERR', 'GAIN', 'SIM_MAGOBS'] )

        # Convert to polars DataFrame, byteswapping as necessary
        dtypes = [ photrows[c].dtype if photrows[c].dtype.isnative else photrows[c].dtype.name
                   for c in photrows.dtype.names ]
        df = polars.from_dict( { c: polars.Series( photrows[c].astype(d) )
                                 for c, d in zip( photrows.dtype.names, dtypes ) } )
        # Because FITS has fixed-width strings, strip the meaningless spaces from
        #   the end of the BAND field
        df = df.with_columns( polars.col('BAND').str.strip_chars() )

        # Remove some columns we don't care about:
        df = df.select( 'MJD', 'BAND', 'PHOTFLAG', 'PHOTPROB', 'FLUXCAL', 'FLUXCALERR',
                        'PSF_SIG1', 'SKY_SIG', 'RDNOISE', 'ZEROPT', 'ZEROPT_ERR', 'GAIN', 'SIM_MAGOBS' )

        if return_format == 'pandas':
            return df.to_pandas()
        else:
            return df


    def get_ltcv( self, obj_class_name, snid, return_format='polars' ):
        """Read the lightcurve of a single object.

        Don't write a for loop where you read thousands of lightcurves
        by calling this function repeatedly.  For bulk processing of all
        lightcurves, look at get_all_ltcvs().

        Speed notes:

          * The first time you call this for a given class, it will be
            slower, because it has to read all the HEAD files (unless
            you preceeded this with a call to get_head).  Subsequent
            calls *for the same class* will be faster, because the head
            file is cached.

          * This will be relatively slow if you are using gzipped SNANA
            files, because it has to read and ungzip the entier PHOT
            file.  If you're using FITS files that aren't gzipped, then
            if your filesystem supports it, memory-mapping will allow
            the reader to skip to the line of the object you're looking
            for, and the read should be faster.

        Parameters
        ----------
          obj_class_name : str
            The object class name, e.g. "AGN", "SNIa-SALT3".  Must be one
            of the elements of the list self.obj_class_names

          snid : int (or numpy.int64)
            The object ID of the object to be read.  This is from the
            'SNID' field of the data frame returned by get_head().  (Our
            supernova bias can be seen by the name of this field.)

        Returns
        --------
          pandas DataFrame with the multi-band lightcurve of the requested object.

          Columns are:
            MJD, BAND, PHOTFLAG, PHOTPROB, FLUXCAL, FLUXCALERR, PSF_SIG1,
            SKY_SIG, RDNOISE, ZEROPT, ZEROPT_ERR, SIM_MAGOBS

        """

        head = self.get_head( obj_class_name )
        headrow = head.filter( polars.col("SNID") == snid )
        if len( headrow ) == 0:
            raise ValueError( f"Unknown {obj_class_name} object id {snid}" )
        if len( headrow ) > 1:
            raise RuntimeError( f"Found multiple {obj_class_name} with object id {snid}; this shouldn't happen!" )

        # Off by one: FITS starts counting at 1, but we index arrays from 0
        ptrmin = headrow['PTROBS_MIN'][0] - 1
        # ptrmax is actually one past the max (hence no -1 here)
        ptrmax = headrow['PTROBS_MAX'][0]

        photfile = self.phots[obj_class_name][headrow['file_num'][0]]
        self.logger.info( f"Reading lightcurve from {photfile}" )
        df = self._read_one_phot_file( photfile, ptrmin, ptrmax, return_format=return_format )
        return df


    def get_all_ltcvs( self, obj_class_name, file_num=None, return_format='polars', agg=False,
                       include_header=False, include_truth=False ):
        """Get all lightcuvres of a class (optionally from one PHOT file)

        You probably want to set file_num; otherwise, this is likely to
        be very slow and will use a gigantic amount of memory (depending
        on the object class; for instance, SNIa-SALT3 uses 41GB).  For a
        large class of objects (e.g. SNIa-SALT3), expect the read time
        for a single file_num to be of order 10s of seconds for gzipped
        PHOT files.  (This means, for instance, that reading all
        lightcurves for SNIa-SALT3 will take up to tens of minutes.)

        If you really need to go through all the lightcurves, do this
        inside a "for file_num in range(1,41)" loop, or something like
        that.  You'll still end up having to read everything, so it will
        still take a long time, but you won't ever use as much memory at
        once.

        Parameters
        ----------
          obj_class_name : str
            The object class name, e.g. "AGN", "SNIa-SALT3".  Must be one
            of the elements of the list self.obj_class_names


          full_header_info : bool, default True
            If True, the resultant data frame will include the header
            columns (see "Returns") below.  IF False, it will only
            include the lightcurve columns.

          file_num : int or None
            If None, will read all PHOT files for the object type.  This
            will be slow.  If int, between 1 and 40, will just read that
            phot file.

          return_format : str, default 'polars'
            One of 'polars' or 'pandas'

          agg : bool, default False
            If False, get back a data frame with one row per photometry
            point.  If True, get back a data frame with one row per
            object.  See "Returns" below.

          include_header : bool, default False
            Ignored if agg is False.  If full_header is False, then each
            row of the aggregated DataFrame will only have the
            lightcurve information (from the phot file).  If full_header
            is True, then each row of the DataFrame will also have
            all the header information for the object.

          include_truth : bool, default False
            Like include_header, but for the truth file.  Using both
            include_header and include_truth will lead to a lot of
            redundant information, as much of the truth information is
            already in the head files in the SIM_* columns.  (E.g. there
            will be columns PEAKMAG_g and SIM_PEAKMAG_g that have the
            same information.)

        Returns
        -------
          A pandas or polars DataFrame (based on return_format)

          * If agg==False

            A DataFrame with the multi-band lightcurve of
            all objects (or the subset of objects from file_num) of the
            requested type, sorted by SNID, BAND, MJD.

            The data frame is indexed by SNID and BAND.  It has lightcurve columns,
            each of which is a list; all lists for a given SNID have the
            same length.  The lightcurve columns are:
                MJD : float
                BAND : object (single character string)
                PHOTFLAG : int
                FLUXCAL : float
                FLUXCALERR : float
                PSF_SIG1 : float
                SKY_SIG : float
                RDNOISE : float
                ZEROPT : float
                ZEROPT_ERR : float
                SIM_MAGOBS : float

            full_header is ignored in this case

          * If agg==True:

            TODO

        """

        if return_format not in ( 'polars', 'pandas', 'polars_nested' ):
            raise ValueError( "Unknown return_format {return_format}" )

        head = self.get_head( obj_class_name )
        if file_num is not None:
            head = head.filter( polars.col('file_num') == f'{int(file_num):04d}' )
            if len( head ) == 0:
                raise ValueError( f"No {obj_class_name} with file_num {file_num}" )
            nums = [ f'{int(file_num):04d}' ]
        else:
            nums = [ f'{i:04d}' for i in range(1,41) ]

        dfs = []
        for num in nums:
            photfile = self.phots[obj_class_name][num]
            self.logger.info( f"Reading {photfile}..." )
            df = self._read_one_phot_file( photfile )
            self.logger.info( "...assigning SNID" )
            # This is incredibly slow.
            # Is there a faster way than the with_columns and scatter business?
            # I'm just looking for an equivalent to pandas df.loc[ptrmin:ptrmax, 'SNID'] = snid
            # df = df.with_columns( SNID=polars.lit( -999, dtype=polars.Int64 ) )
            # for row in head.filter( polars.col('file_num') == f'{int(num):04d}' ).iter_rows( named=True ):
            #     ptrmin = row['PTROBS_MIN'] - 1
            #     ptrmax = row['PTROBS_MAX']
            #     df = df.with_columns( df['SNID'].scatter( range(ptrmin, ptrmax ), row['SNID'] ) )
            snids = []
            for row in head.filter( polars.col('file_num') == f'{int(num):04d}' ).iter_rows( named=True ):
                ptrmin = row['PTROBS_MIN'] - 1
                ptrmax = row['PTROBS_MAX']
                snids.extend( [row['SNID']] * (ptrmax-ptrmin) )
                snids.append( -999 )
            df = df.with_columns( polars.Series( name='SNID', values=snids ) )

            # The phot file will have had a bunch of "separator" rows where (among other things)
            #   MJD was -777.  Those should all have SNID=-999; trim them out.
            df = df.filter( polars.col('SNID') >= 0 )

            dfs.append( df )

        self.logger.debug( f"Concatenating {len(dfs)} dataframes" )
        df = polars.concat( [ d for d in dfs if len(d) > 0 ] ) if len(dfs) > 1 else dfs[0]
        self.logger.debug( f"Sorting" )
        df = df.sort( [ 'SNID', 'BAND', 'MJD' ] )

        if agg:
            self.logger.debug( "Aggregating" )
            cols = [ polars.col(c) for c in df.columns if c != 'SNID' ]
            df = df.group_by( 'SNID' ).agg( *cols )
            if include_header:
                self.logger.debug( "Joining head" )
                df = df.join( head, on='SNID' )
                df.drop_in_place( 'file_num' )
                df.drop_in_place( 'head_filename' )
            if include_truth:
                self.logger.debug( "Getting truth" )
                truth = self.get_object_truth( obj_class_name )
                self.logger.debug( "Joning truth" )
                df = df.join( truth, on='SNID' )
            self.logger.debug( "Sorting" )
            df = df.sort( 'SNID' )

        self.logger.debug( "Returning" )
        if return_format == 'polars':
            return df
        elif return_format == 'pandas':
            return df.to_pandas()
        else:
            raise RuntimeError( "This should never happen" )
