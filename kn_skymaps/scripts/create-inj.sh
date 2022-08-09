lalapps_inspinj \
	-o inj.xml \
	--m-distr source \
	--mass-file masses.dat \
	--disable-spin \
	--t-distr uniform \
	--gps-start-time 1000000000 \
	--gps-end-time 1000400000 \
	--time-step 200 \
	--l-distr source \
	--source-file locations.dat \
	--i-distr uniform \
	--f-lower 30 --disable-spin \
	--waveform TaylorF2threePointFivePN \
	--d-distr source \
	--disable-milkyway \
	--seed 1234
	#--sourcecomplete \
	#--seed 1234
	#--fixed-mass1 1.4 --fixed-mass2 1.4 \
	#--min-distance 50e3 --max-distance 400e3 \
	#--m-distr componentMass --min-mass1 1.0 --max-mass1 2.5 --min-mass2 1.0 --max-mass2 2.5 \
	# --max-mtotal 4.0 \
