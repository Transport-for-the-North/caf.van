Van Model Inputs
================

The Van model has a number of input files which can be provided in the
GUI, or via a configuration file (example below). This section details
all of the input files which are needed in order to run the Van model.

To run the Van model with a configuration file it needs to be ran from
command line. The command for running it is
``python -m LFT.lgv_model -c "path/to/config.yml"``, this command
should be ran from the Anaconda prompt after activating the environment
(see `Running Local Freight Tool <#running-local-freight-tool>`__ for
more information). An example of the configuration file is shown below.

.. note::
   Help text for running the tool through the command line can
   be seen with ``python -m LFT.lgv_model -h`` and an example config file
   can be created with the command ``python -m LFT.lgv_model -e``.


.. todo::
   Update the example config below to reflect recent changes.

.. code:: yaml

   household_paths:
     name: LGV Households
     path: CSV of households data
     zc_path: Zone correspondence CSV
   bres_path: Path to the BRES data CSV at LSOA level
   warehouse_path: Path for the warehouse floorspace data CSV at LSOA level
   commute_warehouse_paths:
     medium: CSV of LSOA warehouse floorspace for commute segment (medium weighting),
       required
     low: CSV of LSOA warehouse floorspace for commute segment (low weighting), optional
     high: CSV of LSOA warehouse floorspace for commute segment (high weighting), optional
   parameters_path: Path to parameters spreadsheet
   qs606ew_path: Path to the England & Wales Census Occupation data CSV
   qs606sc_path: Path to the Scottish Census Occupation data CSV
   sc_w_dwellings_path: Path to the Scottish and Welsh dwellings data CSV
   e_dwellings_path: Path to the English dwellings data XLSX
   ndr_floorspace_path: Path to the NDR Business Floorspace CSV.
   lsoa_lookup_path: Path to the LSOA to model zone correspondence CSV
   msoa_lookup_path: Path to the MSOA to model zone correspondence CSV
   lad_lookup_path: Path to the Local Authority District to model zone correspondence CSV
   model_study_area: Path to CSV containing lookup for zones in model study area
   cost_matrix_path: Path to CSV containing cost matrix, should be square matrix with
     zone numbers as column names and indices
   calibration_matrix_path: Path to CSV containing calibration matrix, should be square
     matrix with zone numbers as column names and indices
   trip_distributions_path: Path to Excel Workbook containing all the trip cost distributions
   output_folder: Path to folder to save outputs to

Household Projections & Zone Correspondence
-------------------------------------------

UK households projections for the model year at MSOA level, data can be
extracted from TEMPro. This data should contain the number of households
per MSOA for the model year. The data extracted from TEMPro contains a
number of columns only two of which are required for the model, these
are summarised in the table below, any additional columns are ignored.
This data should be provided in a comma-separated values (CSV) file.

.. table:: Required columns for the UK household projections data

   +-------------+------+-------------------------------------------------+
   | Column      | Data | Description                                     |
   | Name        | Type |                                                 |
   +=============+======+=================================================+
   | Area        | Text | MSOA area code e.g. E02003616                   |
   | Description |      |                                                 |
   +-------------+------+-------------------------------------------------+
   | HHs         | Real | The number of households projected to be in     |
   |             |      | that MSOA zone                                  |
   +-------------+------+-------------------------------------------------+
   | Jobs        | Real | The number of jobs projected to be in that MSOA |
   |             |      | zone                                            |
   +-------------+------+-------------------------------------------------+

In addition to the households data the model also requires a zone
correspondence file which provides the lookup between the MSOA and the
model zones, the correspondence file requires three columns which are
summarised in the table below. The zone correspondence file can be
created using CAF.Space.

.. table:: Required columns for the UK household zone correspondence,
   column names are ignored the columns just need to be in the correct
   order.

   ====== ========= ===================================
   Column Data Type Description
   ====== ========= ===================================
   1      Text      MSOA area code e.g. E02003616
   2      Integer   Corresponding model zone ID
   3      Real      Splitting factor for correspondence
   ====== ========= ===================================

BRES Data
---------

The Business Register and Employment Survey (BRES) is available from
`NOMIS <https://www.nomisweb.co.uk/datasets/newbres6pub>`__ and contains
the number of employees for different industrial sectors at LSOA
(Scottish data zone) level, at time of writing the data is provided up
to 2019. The van model requires the data to be extracted for all LSOAs
(England and Wales) and data zones (Scotland) at the model year, all
broad industrial groups and all employees should be included in the
output.

The model expects the file to be saved as a comma-separated values (CSV)
file with the first eight rows used for meta data and the column names
on row nine, all required columns are listed in the table below. The
BRES data is expected to be provided at LSOA level, the LSOA zone
correspondence file discussed in `Other Zone
Correspondences <#other-zone-correspondences>`__ will be used to
translate the BRES data to the model zone system.

.. csv-table:: Required columns for the BRES data, column names must be exactly as listed.
      Any columns not listed will be ignored.
   :file: ../_static/tables/bres_data_columns.csv
   :widths: 50, 5, 45
   :header-rows: 1

Warehouse Data
--------------

Warehouse floorspace area data is used for calculating trip ends for the
delivery and commute segments. The warehouse floorspace data used by
Transport for the North is aggregated from Ordnance Survey's Address
Base Premium and Master map data.

The following four warehouse floorspace input files are required (all at
LSOA zoning):

-  Warehouse floorspace for delivery stem productions, required
-  Warehouse floorspace for attracting LGV commuting drivers

   -  Medium relevance floorspace, required
   -  High relevance floorspace, optional
   -  Low relevance floorspace, optional

All the warehouse floorspace input files are in the same format, they
should be a CSV file with two columns, as defined in the table below.

.. table:: Column definitions for the warehouse floorspace input files.

   +--------------+------------+------------------------------------+
   | Column Name  | Data Type  | Description                        |
   +==============+============+====================================+
   | LSOA11CD     | Text       | LSOA zone ID.                      |
   +--------------+------------+------------------------------------+
   | area         | Real       | Total warehouse floorspace for the |
   |              |            | LSOA (:math:`m^2`).                |
   +--------------+------------+------------------------------------+

.. note::
   Any missing LSOAs are assumed to have zero floorspace.

Van Parameters Spreadsheet
--------------------------

This input should be an Excel spreadsheet containing a variety of sheets
with different parameters for the van model. Each of the required sheets
in this input file are discussed in the following sections.

.. todo::
   Update documentation on parameters spreadsheet to reflect recent changes.

Parameters
~~~~~~~~~~

The sheet named "Parameters" should contain two columns with the headers
"Parameter" and "Value". The following table gives the names of the
parameters and a description of what value should be provided.

.. table:: Required parameters for the Van Model, parameters must be
   labelled exactly as given.

   +----------------+-----------+---------------------------------------------+
   | Parameter      | Data Type | Description                                 |
   +================+===========+=============================================+
   | LGV growth     | Real      | A factor to increase the LGV trips from the |
   |                |           | van survey year to the model year           |
   +----------------+-----------+---------------------------------------------+
   | Average new    | Real      | The average new house size in :math:`m^2`   |
   | house size     |           |                                             |
   +----------------+-----------+---------------------------------------------+
   | Scotland       | Real      | The proportion of SOC821 occupations        |
   | SOC821 / SOC82 | (0 - 1)   | in the SOC82 segment.                       |
   +----------------+-----------+---------------------------------------------+
   | Model Year     | Integer   | The model year e.g. 2018                    |
   +----------------+-----------+---------------------------------------------+

Commute Trips by Main Usage
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named "Commute trips by main usage" should contain the annual
number of commute van trips from the van survey by usage type. The
following usage types should be included:

-  G: Carryings goods
-  S: Service / trades
-  C: Commuting
-  T: Carrying people
-  O: Other

This sheet should have two columns with the headers in the first row,
the table below lists the columns.

.. table:: Required columns for the commute trips by main usage sheet.

   =========== ============= ============================================================
   Column Name Data Type     Description
   =========== ============= ============================================================
   Main Usage  Character (1) Usage code for each of the types listed above
   Trips       Real          The annual number of commuting LGV trips for that usage type
   =========== ============= ============================================================

Commute Trips by Land Use
~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named "Commute trips by land use" should contain the annual
number of commute van trips from the van survey by land use type. The
following land uses should be included:

-  Residential
-  Construction
-  Employment

This sheet should have two columns with the headers in the first row,
the table below lists the columns.

.. table:: Required columns for the commute trips by land use sheet.

   +---------------+------+-----------------------------------------------+
   | Column Name   | Data | Description                                   |
   |               | Type |                                               |
   +===============+======+===============================================+
   | Land use at   | Text | The name of the land use type                 |
   | trip end      |      | e.g. Residential                              |
   +---------------+------+-----------------------------------------------+
   | Trips         | Real | The annual number of commuting LGV trips for  |
   |               |      | that land use                                 |
   +---------------+------+-----------------------------------------------+

Annual Service Trips
~~~~~~~~~~~~~~~~~~~~

The sheet named "Annual Service Trips" should contain the annual number
of LGV service trips by land use type from the DfT van survey. The sheet
should contain the following land uses:

-  Residential
-  Office
-  All Other

This sheet should have two columns with the headers in the first row,
the table below lists the columns.

.. table:: Required columns for the annual service trips sheet.

   +---------------+------+----------------------------------------------+
   | Column Name   | Data | Description                                  |
   |               | Type |                                              |
   +===============+======+==============================================+
   | Segment       | Text | The name of the land use type                |
   |               |      | e.g. Residential                             |
   +---------------+------+----------------------------------------------+
   | Annual        | Real | The annual number of LGV service trips for   |
   | Service Trips |      | that land use                                |
   +---------------+------+----------------------------------------------+

Delivery Segment Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet name "Delivery Segment Parameters" contains various mandatory
parameters, listed in the table below. The sheet should have the column
headers "Parameter" and "Value" on the first row.

.. csv-table:: Required parameters for the delivery segment sheet,
   parameters should be named exactly as written.
   :file: ../_static/tables/delivery_sheet_columns.csv
   :header-rows: 1
   :widths: 20, 10, 70

Commute Warehouse Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named "Commute Warehouse Parameters" should contain all the
parameters for the warehouse input calculations, including the weighting
factors and infilling parameters. The table below describes all the
required values and their use, the different weighting factors
correspond to the input files described in :ref:`warehouse data`.

.. csv-table:: Description of the commute warehouse parameters
   :file: ../_static/tables/commute_parameters_columns.csv
   :header-rows: 1
   :widths: 20, 10, 70

Zone infill method calculates an infill value after all the warehouse
data has been factored and combined and then infills any zones in the
"Model Zone Infill" list, which don't contain non-zero values already.
The following methods can be chosen for calculating the infill value:

-  min: minimum value from existing data (including zeros)
-  mean: mean value from existing data
-  median: median value from existing data
-  non_zero_min: minimum non-zero value from existing data
-  zero: infills zones with zero

Gravity Model Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named "Gravity Model Parameters" should contains parameters
for the gravity model for each of the six van model segments (Service,
Delivery Parcel Stem, Delivery Parcel Bush, Delivery Grocery, Commuting
Drivers and Commuting Skilled Trades). The sheet contains six columns,
listed in the table below, with the headers on the first row.

.. todo:: Move description of these to config where they now are

.. table:: Required columns for the gravity model parameters sheet.

   +--------+---------+--------------------------------------------------+
   | Column | Data    | Description                                      |
   | Name   | Type    |                                                  |
   +========+=========+==================================================+
   | S      | Text    | The name of the van model segment e.g. Service   |
   | egment |         |                                                  |
   +--------+---------+--------------------------------------------------+
   | F      | Text    | The type of furnessing to do, see `Gravity       |
   | urness | (DOUBLE | Model <#gravity-model>`__ for more details.      |
   | Cons   | or      | These can be provided in uppercase or lowercase. |
   | traint | SINGLE) |                                                  |
   | Type   |         |                                                  |
   +--------+---------+--------------------------------------------------+
   | Cost   | Text    | The cost function to use, see `Gravity           |
   | Fu     | (tanner | Model <#gravity-model>`__ for more details.      |
   | nction | or log  | These can be provided in uppercase or lowercase. |
   |        | normal) |                                                  |
   +--------+---------+--------------------------------------------------+
   | Cost   | Real    | The first variable for the cost function,        |
   | Fu     |         | :math:`\alpha` for tanner and :math:`\sigma` for |
   | nction |         | log normal                                       |
   | Par    |         |                                                  |
   | ameter |         |                                                  |
   | 1      |         |                                                  |
   +--------+---------+--------------------------------------------------+
   | Cost   | Real    | The second variable for the cost function,       |
   | Fu     |         | :math:`\beta` for tanner and :math:`\mu` for log |
   | nction |         | normal                                           |
   | Par    |         |                                                  |
   | ameter |         |                                                  |
   | 2      |         |                                                  |
   +--------+---------+--------------------------------------------------+
   | Run    | Text    | Whether or not to calibrate the gravity model to |
   | Calib  | (Yes or | the trip distribution, uses cost function        |
   | ration | No)     | parameters as starting point                     |
   +--------+---------+--------------------------------------------------+

Time Period Factors
~~~~~~~~~~~~~~~~~~~

The sheet named "Time Period Factors" should contain all the factors for
converting from the annual matrices to the time periods for each model
segment, see Ian Williams' technical note[^lgvn_design] for more detail
on each segment. The table should contain one factor for each time
period / segment combination, a list of the required columns is given
below.

The time period factors (:math:`f_{tp}`) are multiplied by the annual
matrix (:math:`M_{annual}`) to get the time period matrix
(:math:`M_{tp}`) using the formula below. This calculation is done for
each segment and time period separately.

.. math::


   M_{tp} = M_{annual} \times f_{tp}

.. note::
   The time period factors are expected to convert from annual
   trips to average daily time period, therefore each factor should be less
   than, approximately, 1/365.

.. table:: Required columns for the time period factors sheet.

   +----------------+------+--------------------------------------------------------+
   | Column Names   | Data | Description                                            |
   |                | Type |                                                        |
   +================+======+========================================================+
   | Time           | Text | The name of the time period, will be used for naming   |
   | Period         |      | the outputs.                                           |
   +----------------+------+--------------------------------------------------------+
   | Service        | Real | The factor to multiply the annual matrix by to get the |
   |                |      | average daily time period (e.g. AM) for this segment.  |
   +----------------+------+--------------------------------------------------------+
   | Delivery       | Real | The factor to multiply the annual matrix by to get the |
   | Parcel Stem    |      | average daily time period (e.g. AM) for this segment.  |
   +----------------+------+--------------------------------------------------------+
   | Delivery       | Real | The factor to multiply the annual matrix by to get the |
   | Parcel Bush    |      | average daily time period (e.g. AM) for this segment   |
   +----------------+------+--------------------------------------------------------+
   | Delivery       | Real | The factor to multiply the annual matrix by to get the |
   | Grocery        |      | average daily time period (e.g. AM) for this segment   |
   +----------------+------+--------------------------------------------------------+
   | Commuting      | Real | The factor to multiply the annual matrix by to get the |
   | Drivers        |      | average daily time period (e.g. AM) for this segment   |
   +----------------+------+--------------------------------------------------------+
   | Commuting      | Real | The factor to multiply the annual matrix by to get the |
   | Skilled Trades |      | average daily time period (e.g. AM) for this segment   |
   +----------------+------+--------------------------------------------------------+

LGV Trip Distributions Spreadsheet
----------------------------------

The trip distributions spreadsheet should contain a sheets with
distributions for the different segments. The worksheets should be named
"Commuting", "Service", "Delivery" and "Delivery Bush" and will be used
for the relevant segment. Each worksheet should have the name of the
cost distribution and it's units in cell A1, e.g. "Average Length (km)",
and the column headers for the distribution table in row two. The
distribution tables require four columns which are listed in the table
below.

.. table:: Required columns for the trip distribution tables, column
   headers should be on row two of each sheet.

   +-------------+------+-----------------------------------------------------------+
   | Column Name | Data | Description                                               |
   |             | Type |                                                           |
   +=============+======+===========================================================+
   | observed    | Real | The number of observed trips in this bin                  |
   +-------------+------+-----------------------------------------------------------+
   | start       | Real | The start (inclusive) of the bin in the same units as the |
   |             |      | `Cost Matrix <#cost-matrix>`__                            |
   +-------------+------+-----------------------------------------------------------+
   | end         | Real | The end (exclusive) of the bin in the same units as the   |
   |             |      | `Cost Matrix <#cost-matrix>`__                            |
   +-------------+------+-----------------------------------------------------------+
   | average     | Real | The weighted average of the cost value for this bin, in   |
   |             |      | the same units as the `Cost Matrix <#cost-matrix>`__      |
   +-------------+------+-----------------------------------------------------------+

Census Occupation Data
----------------------

The census occupation data is provided to the tool in two separate
comma-separated values (CSV) files, both of which are available on the
`NOMIS website <https://www.nomisweb.co.uk/>`__. The census tables
required are QS606EW and QS606UK, both tables contain meta data in the
first eight rows and the column names on row nine.

The QS606EW census table contains occupation data for England and Wales
at LSOA level, and more occupation categories, a list of the expected
columns is given in the table below. The table should be provided with
the units persons.

.. table:: Required columns for the QS606EW occupation data CSV.

   +-------------------------------+---------+-------------------------+
   | Column Name                   | Data    | Description             |
   |                               | Type    |                         |
   +===============================+=========+=========================+
   | 2011 super output area -      | Text    | LSOA name               |
   | lower layer                   |         |                         |
   +-------------------------------+---------+-------------------------+
   | mnemonic                      | Text    | LSOA area code          |
   +-------------------------------+---------+-------------------------+
   | All categories: Occupation    | Integer | Total occupation        |
   +-------------------------------+---------+-------------------------+
   | 51. Skilled agricultural and  | Integer | Occupation numbers for  |
   | related trades                |         | this segment            |
   +-------------------------------+---------+-------------------------+
   | 52. Skilled metal, electrical | Integer | Occupation numbers for  |
   | and electronic trades         |         | this segment            |
   +-------------------------------+---------+-------------------------+
   | 53. Skilled construction and  | Integer | Occupation numbers for  |
   | building trades               |         | this segment            |
   +-------------------------------+---------+-------------------------+
   | 821. Road Transport Drivers   | Integer | Occupation numbers for  |
   |                               |         | this segment            |
   +-------------------------------+---------+-------------------------+

The QS606UK census table should contain the occupation data extracted
for Scotland only at datazone level and should be provided with the
units persons. The expected columns for this input are shown in the
table below.

.. table:: Required columns for the QS606UK occupation data CSV.

   +---------------------------------------+-----+------------------------+
   | Column Name                           | D   | Description            |
   |                                       | ata |                        |
   |                                       | T   |                        |
   |                                       | ype |                        |
   +=======================================+=====+========================+
   | 2011 scottish datazone                | T   | Datazone name          |
   |                                       | ext |                        |
   +---------------------------------------+-----+------------------------+
   | mnemonic                              | T   | Datazone area code     |
   |                                       | ext |                        |
   +---------------------------------------+-----+------------------------+
   | All categories: Occupation            | I   | Total occupation       |
   |                                       | nte |                        |
   |                                       | ger |                        |
   +---------------------------------------+-----+------------------------+
   | 51. Skilled agricultural and related  | I   | Occupation numbers for |
   | trades                                | nte | this segment           |
   |                                       | ger |                        |
   +---------------------------------------+-----+------------------------+
   | 52. Skilled metal, electrical and     | I   | Occupation numbers for |
   | electronic trades                     | nte | this segment           |
   |                                       | ger |                        |
   +---------------------------------------+-----+------------------------+
   | 53. Skilled construction and building | I   | Occupation numbers for |
   | trades                                | nte | this segment           |
   |                                       | ger |                        |
   +---------------------------------------+-----+------------------------+
   | 82. Transport and mobile machine      | I   | Occupation numbers for |
   | drivers and operatives                | nte | this segment           |
   |                                       | ger |                        |
   +---------------------------------------+-----+------------------------+

Dwellings Data
--------------

The dwellings data is provided to the tool in two separate files, an
Excel Workbook containing the English data and a CSV containing the
Scottish and Welsh data.

The English dwellings data is provided, at Local Authority District
(LAD), in Table 123 on the `Live tables on housing supply: net additional dwellings
<https://www.gov.uk/government/statistical-data-sets/live-tables-on-net-supply-of-housing>`__
page of the UK government website. The data is expected to be converted
to an Excel workbook before providing to the tool but no changes to the
formatting should be made, the workbook should have sheets labelled with
the year of the data (e.g. 2018-19) and should contain the model year.
The worksheet is expected to have the column names on row 4, a list of
the required columns is given in the table below

.. table:: English dwellings data required columns, names of columns
   should be exactly as listed any other columns are ignored.

   +--------------------------+-----+------------------------------------+
   | Column Name              | D   | Description                        |
   |                          | ata |                                    |
   |                          | T   |                                    |
   |                          | ype |                                    |
   +==========================+=====+====================================+
   | CurrentONS code          | T   | LAD area code e.g. E06000055       |
   |                          | ext |                                    |
   +--------------------------+-----+------------------------------------+
   | Lower and Single Tier    | T   | Name of the LAD                    |
   | Authority Data           | ext |                                    |
   +--------------------------+-----+------------------------------------+
   | Demolitions              | I   | Number of building demolitions     |
   |                          | nte | during the year                    |
   |                          | ger |                                    |
   +--------------------------+-----+------------------------------------+
   | Net Additions            | I   | Net number of building additions   |
   |                          | nte | during the year                    |
   |                          | ger |                                    |
   +--------------------------+-----+------------------------------------+

The Scottish and Welsh dwellings data should be input as one CSV
containing the values for both countries, both datasets can be
downloaded off the internet separately. The Scottish data is available
within `National Records of Scotland Household Estimates
<https://www.nrscotland.gov.uk/statistics-and-data/statistics/statistics-by-theme/households/household-estimates/2019>`__
dataset, table 2 contains the number of dwellings by council area for
recent years. The Welsh data is available on the `Dwelling stock estimates page
<https://statswales.gov.wales/Catalogue/Housing/Dwelling-Stock-Estimates/dwellingstockestimates-by-localauthority-tenure>`__
of the StatsWales website and should be obtained for the model year and
the model year plus one. The data should be combined and provided to the
tool as a CSV, the required columns are given in the table below.

.. table:: Scottish and Welsh dwellings data required columns.

   +--------------------+------+------------------------------------------+
   | Column Name        | Data | Description                              |
   |                    | Type |                                          |
   +====================+======+==========================================+
   | zone               | Text | The LAD area code e.g. W06000013         |
   +--------------------+------+------------------------------------------+
   | lad19nm            | Text | The name of the LAD e.g. Bridgend        |
   +--------------------+------+------------------------------------------+
   | model year         | Int  | The number of dwellings in each LAD for  |
   | (e.g. 2018)        | eger | the model year                           |
   +--------------------+------+------------------------------------------+
   | model year + 1     | Int  | The number of dwellings in each LAD for  |
   | (e.g. 2019)        | eger | the next year                            |
   +--------------------+------+------------------------------------------+

NDR Business Data
-----------------

The non-domestic rating business floorspace data is available in the NDR
Business Floorspace tables Excel spreadsheet on `GOV.UK
<https://www.gov.uk/government/statistics/non-domestic-rating-stock-of-properties-including-business-floorspace-2019>`__
for the whole UK. The tables provide the business floorspace by
administrative area for various years and different sectors, the tool
requires the data from the various tables to be compiled into a single
CSV which contains different columns for the different sectors (Retail,
Office, Industrial and Other) and years. The table below details the
columns required in the input CSV file.

.. table:: NDR business floorspace CSV required columns.

   +-----------------+----+-----------------------------------------------+
   | Column Name     | Da | Description                                   |
   |                 | ta |                                               |
   |                 | Ty |                                               |
   |                 | pe |                                               |
   +=================+====+===============================================+
   | AREA_CODE       | Te | Area code e.g. E92000001                      |
   |                 | xt |                                               |
   +-----------------+----+-----------------------------------------------+
   | AREA            | Te | Name of area e.g. ENGLAND                     |
   |                 | xt |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace      | I  | Floorspace in :math:`1000m^2` for the retail  |
   | _2017-18_Retail | nt | sector ending in the model year               |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace      | I  | Floorspace in :math:`1000m^2` for the retail  |
   | _2018-19_Retail | nt | sector starting in the model year             |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace      | I  | Floorspace in :math:`1000m^2` for the office  |
   | _2017-18_Office | nt | sector ending in the model year               |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace      | I  | Floorspace in :math:`1000m^2` for the office  |
   | _2018-19_Office | nt | sector starting in the model year             |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace_201  | I  | Floorspace in :math:`1000m^2` for the         |
   | 7-18_Industrial | nt | industrial sector ending in the model year    |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspace_201  | I  | Floorspace in :math:`1000m^2` for the         |
   | 8-19_Industrial | nt | industrial sector starting in the model year  |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspac       | I  | Floorspace in :math:`1000m^2` for the other   |
   | e_2017-18_Other | nt | sectors ending in the model year              |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+
   | Floorspac       | I  | Floorspace in :math:`1000m^2` for the other   |
   | e_2018-19_Other | nt | sectors starting in the model year            |
   |                 | eg |                                               |
   |                 | er |                                               |
   +-----------------+----+-----------------------------------------------+

.. note::
   The column names should include the actual model year (and the
   years before and after) instead of 2018.

Other Zone Correspondences
--------------------------

Three other more generic zone correspondence CSVs are required for
converting LSOAs, MSOAs and LADs to the model zone system. These
correspondence files are used for converting the :ref:`census occupation data`,
:ref:`dwellings data` and :ref:`ndr business data`. All zone correspondence
CSV files have the same format with column names on the first row and
three required columns, listed in the table below.

.. table:: Required columns for the zone correspondence CSVs, column
   names are ignored the columns just need to be in the correct order.

   ====== ========= ===================================
   Column Data Type Description
   ====== ========= ===================================
   1      Text      Area code e.g. E01000001
   2      Integer   Corresponding model zone ID
   3      Real      Splitting factor for correspondence
   ====== ========= ===================================

Study Area Lookup
-----------------

The study area lookup should be a file containing a list of all the
model zones with a second column to flag whether or not they're inside
the model study area. A list of the required columns is given in the
table below.

.. table:: Required columns for the study area lookup CSV, column names
   must be exactly as listed any other columns are ignored.

   +--------+-------------+-----------------------------------------------+
   | Column | Data Type   | Description                                   |
   | Name   |             |                                               |
   +========+=============+===============================================+
   | zone   | Integer     | The model zone number                         |
   +--------+-------------+-----------------------------------------------+
   | in     | Integer (1  | If the zone is inside (1) or outside (0) the  |
   | ternal | or 0)       | study area                                    |
   +--------+-------------+-----------------------------------------------+

.. note:: This should be a complete list of all zones.

Cost Matrix
-----------

Matrix CSV containing the cost values for all zones in the model, the
units of the costs should be the same as the units in the
:ref:`lgv trip distributions spreadsheet`. The CSV file should be in
square matrix format where the first column and row contains all the
zone numbers, an example of a three by three matrix with the same costs
for all zones is shown below.

.. table:: Example 3x3 matrix

   ===== ===== ===== =====
   \     **1** **2** **3**
   ===== ===== ===== =====
   **1** *10*  *10*  *10*
   **2** *10*  *10*  *10*
   **3** *10*  *10*  *10*
   ===== ===== ===== =====

Calibration Matrix
------------------

The calibration matrix should be a CSV in the same format as :ref:`cost matrix`.
This matrix is used during the gravity model
process to adjust the impact of trips between certain zone pairs and
should have positive values around 0 - 2. The :ref:`gravity model` section
outlines the methodology where this input is used.

Output Folder
-------------

The parent directory where all the outputs will be saved. A new
sub-folder will be created with the name convention "LGV Model Outputs -
{date} {time}" (e.g. "LGV Model Outputs - 2021-08-05 19.15.32") will be
created to store the outputs for a single run of the van model.
