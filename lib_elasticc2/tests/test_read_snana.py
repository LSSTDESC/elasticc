# These tests won't pass if you aren't pointing at an exact copy of the original ELAsTiCC2 FITS data files
#
# Run these tests from the lib_elasticc2 directory with
#  TD=<tddir> PYTHONPATH=$PWD:$PYTHONPATH python -m pytest -v tests/test_read_snana.py

import pytest
import pandas
import polars
import numpy
import time

from read_snana import elasticc2_snana_reader

@pytest.fixture
def esr():
    yield elasticc2_snana_reader()

@pytest.fixture
def wastefulesr():
    yield elasticc2_snana_reader( waste_memory_on_heads=True )


def test_obj_class_names( esr ):
    assert esr.obj_class_names == [ 'AGN', 'CART', 'Cepheid', 'EB', 'ILOT', 'KN_B19', 'KN_K17',
                                    'Mdwarf-flare', 'PISN-MOSFIT', 'PISN-STELLA_HECORE',
                                    'PISN-STELLA_HYDROGENIC', 'RRL', 'SL-SN1a', 'SL-SNII', 'SL-SNIb',
                                    'SL-SNIc', 'SLSN-I+host', 'SLSN-I_no_host', 'SNII+HostXT_V19',
                                    'SNII-NMF', 'SNII-Templates', 'SNIIb+HostXT_V19', 'SNIIn+HostXT_V19',
                                    'SNIIn-MOSFIT', 'SNIa-91bg', 'SNIa-SALT3', 'SNIax', 'SNIb+HostXT_V19',
                                    'SNIb-Templates', 'SNIc+HostXT_V19', 'SNIc-Templates',
                                    'SNIcBL+HostXT_V19', 'TDE', 'd-Sct', 'dwarf-nova', 'uLens-Binary',
                                    'uLens-Single-GenLens', 'uLens-Single_PyLIMA' ]

def test_get_object_truth( esr ):
    # Just a spot check, not checking every single one
    with pytest.raises( ValueError, match='Unknown object class name nonexistent' ):
        esr.get_object_truth( 'nonexistent' )
    with pytest.raises( ValueError, match="Unknown return_format foo" ):
        esr.get_object_truth( 'AGN', return_format='foo' )

    truth = esr.get_object_truth( 'AGN' )
    assert isinstance( truth, polars.DataFrame )
    assert set( truth.columns ) == { 'GALID', 'PEAKMJD', 'PEAKMAG_z', 'MU', 'WIDTH_Y', 'PEAKMAG_g', 'GALZPHOTERR',
                                     'ZHELIO', 'WIDTH_z', 'GALZPHOT', 'AV', 'DTSEASON_PEAK', 'MAGSMEAR_COH',
                                     'ZCMB_SMEAR', 'MJD_DETECT_LAST', 'WIDTH_r', 'RA', 'PERIOD', 'PEAKMAG_i',
                                     'NON1A_INDEX', 'WIDTH_g', 'DEC', 'RV', 'GENTYPE', 'NOBS_SATURATE', 'VPEC',
                                     'SIM_SEARCHEFF_MASK', 'LENSDMU', 'SNRMAX2', 'SNRMAX', 'WIDTH_u', 'GALSNSEP',
                                     'GALRANDOM_RADIUS', 'PEAKMAG_u', 'GALNMATCH', 'SNID', 'PEAKMAG_r', 'GALSNDDLR',
                                     'SNRMAX3', 'GALRANDOM_PHI', 'PEAKMAG_Y', 'NOBS', 'LIBID', 'MWEBV', 'ZCMB',
                                     'WIDTH_i', 'MJD_DETECT_FIRST' }
    assert len(truth) == 108556
    assert truth['ZCMB'].min() == pytest.approx( 0.1, abs=0.001 )
    assert truth['ZCMB'].max() == pytest.approx( 2.9, abs=0.001 )

    truth = esr.get_object_truth( 'AGN', return_format='pandas' )
    assert isinstance( truth, pandas.DataFrame )
    assert set( truth.columns.values ) == { 'DEC', 'PERIOD', 'NON1A_INDEX', 'PEAKMAG_u',
                                            'GALSNDDLR', 'GENTYPE', 'SIM_SEARCHEFF_MASK', 'PEAKMJD',
                                            'WIDTH_r', 'RV', 'WIDTH_i', 'GALZPHOT', 'WIDTH_z', 'PEAKMAG_i',
                                            'NOBS_SATURATE', 'WIDTH_g', 'LENSDMU', 'AV', 'WIDTH_u',
                                            'PEAKMAG_g', 'VPEC', 'SNRMAX2', 'SNRMAX', 'MJD_DETECT_LAST',
                                            'SNID', 'GALID', 'MU', 'PEAKMAG_z', 'NOBS', 'GALZPHOTERR',
                                            'SNRMAX3', 'GALSNSEP', 'GALRANDOM_PHI', 'GALNMATCH', 'MWEBV',
                                            'PEAKMAG_r', 'DTSEASON_PEAK', 'PEAKMAG_Y', 'MAGSMEAR_COH',
                                            'RA', 'MJD_DETECT_FIRST', 'ZCMB_SMEAR', 'LIBID', 'ZCMB',
                                            'WIDTH_Y', 'GALRANDOM_RADIUS', 'ZHELIO' }
    assert len(truth) == 108556
    assert truth.ZCMB.min() == pytest.approx( 0.1, abs=0.001 )
    assert truth.ZCMB.max() == pytest.approx( 2.9, abs=0.001 )


def test_get_head( esr, wastefulesr ):
    with pytest.raises( ValueError, match='Unknown object class name nonexistent' ):
        esr.get_head( 'nonexistent' )
    with pytest.raises( ValueError, match="Unknown return_format foo" ):
        esr.get_head( 'AGN', return_format='foo' )

    assert esr._head_cache is None;
    assert esr._head_cache_class is None

    head = esr.get_head( 'AGN' )
    assert len(head) == 108556
    assert id(head) == id(esr._head_cache)
    assert head['SNID'].dtype == polars.Int64
    assert head['SNID'].min() == 1002462
    assert head['SNID'].max() == 159511074
    assert set( head['file_num'] ) == { f'{i:04}' for i in range(1,41) }

    t0 = time.perf_counter()
    head = wastefulesr.get_head( 'AGN' )
    dt_first = time.perf_counter() - t0
    assert len(head) == 108556
    firstcache = wastefulesr._heads_cache['AGN']
    assert id( firstcache ) == id( head )

    t0 = time.perf_counter()
    head = wastefulesr.get_head( 'AGN' )
    dt_second = time.perf_counter() - t0
    # What's a good timing test?  This isn't going to be easily reproducible, as it depends on filesystem speed.
    assert dt_second < dt_first / 2.
    assert id( wastefulesr._heads_cache['AGN'] ) == id( firstcache )

    head = wastefulesr.get_head( 'CART' )
    assert len(head) == 8926
    assert id( wastefulesr._heads_cache['CART'] ) == id( head )

    head = wastefulesr.get_head( 'AGN' )
    assert id( wastefulesr._heads_cache['AGN'] ) == id( firstcache )

    pahead = esr.get_head( 'AGN', return_format='pandas' )
    assert isinstance( pahead, pandas.DataFrame )
    assert len(head) == 108556


def test_get_ltcv( esr ):
    with pytest.raises( ValueError, match='Unknown object class name nonexistent' ):
        esr.get_ltcv( 'nonexistent', 1 )
    with pytest.raises( ValueError, match='Unknown CART object id 1' ):
        esr.get_ltcv( 'CART', 1 )

    # Again, just a spot check
    ltcv = esr.get_ltcv( 'CART', 10388951 )
    assert isinstance( ltcv, polars.DataFrame )
    assert len(ltcv) == 126
    assert set( ltcv['BAND']) == { 'u', 'g', 'r', 'i', 'z', 'Y' }
    assert ltcv['MJD'].min() == pytest.approx( 61086.34, abs=0.01 )
    assert ltcv['MJD'].max() == pytest.approx( 61581.00, abs=0.01 )
    assert ( ltcv['FLUXCAL'] / ltcv['FLUXCALERR'] ).max() == pytest.approx( 5.0, abs=0.1 )

    ltcv = esr.get_ltcv( 'CART', 10388951, return_format='pandas' )
    assert isinstance( ltcv, pandas.DataFrame )
    assert len(ltcv) == 126
    assert set( ltcv['BAND'].values) == { 'u', 'g', 'r', 'i', 'z', 'Y' }
    assert ltcv['MJD'].min() == pytest.approx( 61086.34, abs=0.01 )
    assert ltcv['MJD'].max() == pytest.approx( 61581.00, abs=0.01 )
    assert ( ltcv['FLUXCAL'] / ltcv['FLUXCALERR'] ).max() == pytest.approx( 5.0, abs=0.1 )


def test_get_all_ltcvs( esr ):
    # Use ILOT since there aren't very many so the test will go fast
    ltcvs23 = esr.get_all_ltcvs( 'ILOT', file_num=23 )
    assert len(ltcvs23) == 9827

    # Make sure no -777's slipped through
    assert all( ltcvs23['MJD'] > 60790. )

    # Make sure this is consistent with at leaset one case of get_ltcv
    snid = ltcvs23[ len(ltcvs23) //2 ]['SNID']
    ltcv = esr.get_ltcv( 'ILOT', snid )

    assert len( ltcv ) == len( ltcvs23.filter( polars.col('SNID') == snid ) )
    # Sort ltcv the same way ltcvs23 was sorted
    ltcv = ltcv.sort( [ 'BAND', 'MJD' ] )
    for col in ltcv.columns:
        assert ( ltcv[col] == ltcvs23.filter( polars.col('SNID') == snid )[col] ).all()

    allltcvs = esr.get_all_ltcvs( 'ILOT' )
    assert len(allltcvs) == 295471
    for col in ltcv.columns:
        assert ( ltcv[col] == allltcvs.filter( polars.col('SNID') == snid )[col] ).all()

    allltcvs = esr.get_all_ltcvs( 'ILOT', agg=True )
    assert len(allltcvs) == 1143
    assert set( allltcvs.columns ) == { 'SNID', 'MJD', 'BAND', 'PHOTFLAG', 'PHOTPROB', 'FLUXCAL',
                                        'FLUXCALERR', 'PSF_SIG1', 'SKY_SIG', 'RDNOISE', 'ZEROPT',
                                        'ZEROPT_ERR', 'GAIN', 'SIM_MAGOBS' }
    assert all( allltcvs[c].dtype==polars.List for c in allltcvs.columns if c != 'SNID' )
    assert allltcvs['SNID'].dtype == polars.Int64

    allltcvs = esr.get_all_ltcvs( 'ILOT', agg=True, include_header=True )
    assert len(allltcvs.columns) == 175
    assert allltcvs['SIM_PEAKMAG_g'].dtype == polars.Float32

    allltcvs = esr.get_all_ltcvs( 'ILOT', agg=True, include_truth=True )
    assert len(allltcvs.columns) == 60
    assert allltcvs['PEAKMAG_g'].dtype == polars.Float64

    allltcvs = esr.get_all_ltcvs( 'ILOT', agg=True, include_header=True, include_truth=True )
    assert len(allltcvs.columns) == 221
    assert allltcvs.select( a=(polars.col('SIM_PEAKMAG_g') - polars.col('PEAKMAG_g')).abs() < 0.0001 )['a'].all()




