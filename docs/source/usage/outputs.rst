Van Model Outputs
=================

The Van model creates a new folder for each run to store all outputs inside,
this folder follows the name convention of "LGV Model Outputs - {date}
{time}" (e.g. "LGV Model Outputs - 2021-08-05 19.15.32"). The Van model
outputs are split into three sub-folders "trip ends", "annual trip
matrices" and "time period matrices", the outputs for each are discussed
in the next sections.

Trip Ends
---------

The trip ends folder contains six CSVs, which each contain the trip end
values for each of the following model segments:

-  Service
-  Delivery Grocery
-  Delivery Parcel Bush
-  Delivery Parcel Stem
-  Commute Drivers
-  Commute Skilled Trades

The output files are named after the segments
e.g. ``service_trip_ends.csv`` and they're all saved in the CSV format
with column headers on the first row and three columns. All outputs are
given as production and attraction trip ends, except delivery grocery
and delivery parcel bush which are origin and destinations.

.. table:: Trip ends outputs CSV columns.

   +-------------------+-----+--------------------------------------------+
   | Column Name       | D   | Description                                |
   |                   | ata |                                            |
   |                   | T   |                                            |
   |                   | ype |                                            |
   +===================+=====+============================================+
   | Zone              | I   | The model zone number                      |
   |                   | nte |                                            |
   |                   | ger |                                            |
   +-------------------+-----+--------------------------------------------+
   | Productions (or   | R   | The number of production (or origin) trip  |
   | Origins)          | eal | ends for this zone                         |
   +-------------------+-----+--------------------------------------------+
   | Attractions (or   | R   | The number of attraction (or destination)  |
   | Destinations)     | eal | trip ends for this zone                    |
   +-------------------+-----+--------------------------------------------+

Annual Trip Matrices
--------------------

The annual trip matrices folder contains the following three or four
files for each of the model segments:

-  Annual trip matrix in productions / attractions format (if the model
   segment is in that format)
-  Annual trip matrix in origin / destination format
-  Excel log file
-  PDF trip distributions graph

The following sections discuss each of the above files in more detail.

Annual Trip Matrix
~~~~~~~~~~~~~~~~~~

The annual trip matrix files (both OD and PA) are provided as CSVs in
the square matrix format i.e. the first row and column contain all the
zone numbers and the remaining cells contain the values. All van model
segments have an OD matrix and all, except delivery grocery and delivery
parcel bush, have a PA matrix too. The naming conventions for the two
matrices are as follows:

-  PA: ``{segment_name}-trip_matrix-PA.csv``
-  OD: ``{segment_name}-trip_matrix-OD.csv``

Excel Log File
~~~~~~~~~~~~~~

The Excel log spreadsheet that is created contains various statistics
and results from the van model process. Aggregated statistics are used by
translating the matrix to a higher level summary zone system using the 
summary_zone_translation input. The spreadsheet is named
``{segment_name}-GM_log.xlsx`` and contains the following worksheets:

-  Summary: This sheet contains high-level statistics of the sector aggregated and original 
   matrices. Including mean, min, max, standard deviation, 5%, 25%, 50%, 75% and 95% percentiles,
   sum, number of zeros and almost zeros and number of NaNs. 
-  Trips Ends: This sheet contains the sector aggregated trip ends of the resultant matrix.
-  Matrix: Contains the sector aggregated matrix.
-  Calibration Results: This sheet lists the calibration parameters used
   for the final run of the gravity model and the :math:`R^2` values
   when the matrix is compared against the trip distributions.
-  Furnessing Results: This sheet provides the results of the furnessing
   process on the final run of the gravity model.
-  Trip Distribution: This sheet is a table containing the observed trip
   distribution compared to the matrix distribution.
-  Vehicle Kilometres: This sheet is a table of the total trips and
   vehicle kilometres in the annual OD matrix.
-  Vehicle Kilometres (PA): This sheet contains the same information as
   above but for the PA matrix, if this model segment is PA.

Calibration Log
~~~~~~~~~~~~~~~
Contains the results of each gravity model loop for each TLD category.
The file are named ``gravity_model_{segment_name}-calibration_log.csv``.
Result contained are, attempt ID, loop number, runtime and resultant
cost parameters and convergence for each TLD category 

Trip Distributions Graph
~~~~~~~~~~~~~~~~~~~~~~~~

The PDF contains a graph of the observed trip distributions compared to
the output annual trip matrix distributions. The file is named ``{segment_name}-distribution_{category}.pdf``
and contains the distributions plotted for the observed data and the calibration sub-subset of
the matrix for the TLD category. All the data used to produce these graphs is given in the
Trip Distribution sheet of the :ref:`excel log file`.

Time Period Matrices
--------------------

The time period matrices folder contains a CSV with all the input time
period factors listed and sub-folders for each time period. Each time
period sub-folder contains square matrix CSVs for each of the six model
segments, all matrices have the zones in the first column and row and
have the time period name as a prefix
e.g. ``AM_service-trip_matrix.csv``.
