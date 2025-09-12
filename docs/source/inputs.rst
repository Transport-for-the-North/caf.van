LGV Model Inputs
================

The LGV model has a number of input files which can be provided in the
GUI, or via a configuration file (example below). This section details
all of the input files which are needed in order to run the LGV model.

To run the LGV model with a configuration file it needs to be ran from
command line. The command for running it is
**``python -m LFT.lgv_model -c "path/to/config.yml"``**, this command
should be ran from the Anaconda prompt after activating the environment
(see `Running Local Freight Tool <#running-local-freight-tool>`__ for
more information). An example of the configuration file is shown below.

**Note:** *help text for running the tool through the command line can
be seen with ``python -m LFT.lgv_model -h`` and an example config file
can be created with the command ``python -m LFT.lgv_model -e``.*

.. code:: yaml
  
   zoning: Name of the zoning system to use for the model
   model_zones: Path to CSV containing lookup for zones in model study area.

   household_paths: 
      occupied: Path to the occupied dwellings data DVector
         No specific segmentation is required as it is aggregated to total households by zone.
      zc_path: Path to the zone correspondence CSV.
      unoccupied: Optional - Path to the unoccupied dwellings data DVector. 
         No specific segmentation is required as it is aggregated to total households by zone."""

   employment_paths: 
      path: Path to the TfN Land-use DVector. Required segmentation is 'sic_1_digit'.
      zc_path: Path to the zone correspondence CSV.

   warehouse_path: Path for the warehouse floorspace data CSV at LSOA level
   commute_warehouse_paths:
     medium: CSV of LSOA warehouse floorspace for commute segment (medium weighting),
       required
     low: CSV of LSOA warehouse floorspace for commute segment (low weighting), optional
     high: CSV of LSOA warehouse floorspace for commute segment (high weighting), optional

   parameters_path: Path to the van model parameters Excel workbook.
   qs606ew_path: Path to the England & Wales Census Occupation data CSV
   qs606sc_path: Path to the Scottish Census Occupation data CSV
   constructions_path: Path to GB construction data csv.
   lsoa_lookup_path: Path to the LSOA to model zone correspondence CSV
   tripend_balancing_regions_path: Path to csv containing trip end balancing regions to zone correspondence
   cost_matrix_path: Path to CSV containing cost matrix, should be square matrix with
     zone numbers as column names and indices
   summary_zone_translation: 
      path: Path to model zones to summary zones correspondance CSV
      from_zoning: Name of model zoning system in translation file
      to_zoning: Name of summary zoning system in translation file

   gm_parameters:
      # Separate gravity model parameters for each van segment:
      # service, delivery_parcel_stem, delivery_parcel_bush,
      # delivery_grocery, commuting_drivers, commuting_skilled_trades
      service:
         trip_length_distribution_path: Path to the Trip Length Distribution CSV."""
         cost_function: The cost function to use for the gravity model. Either 'log_normal' or 'tanner'
         cost_function_params: Starting (calibration)/run params for the cost function.
         calibrate: Whether to calibrate the cost function paramas (True) or run with given params (False).
         cat_zone_correspondance_path: Path to CSV with correspondence between the categories in the TLD and the model zones.
         furness_jacobian: Whether to Furness the Jacobian matrix in the gravity model. Find your nearest demand modelling expert for more information.
      delivery_parcel_stem:
         ...
   output_folder: Path to folder to save outputs to
   personal_matrix_inputs:
   # Optional only pass if you want to create a personal matrix
      normits_pa_folder: Path to the full PA Normits matrices, should contain all non home
         based and home based matrices
      normits_to_msoa_lookup: Normits to MSOA(NTEM) lookup, this is NorMITs to model zone lookup as the
         results are taken after normits results are converted back to NoHAM
      normits_to_personal_factor: This is the factor that the personal data should have applied to
         just include van data 4% is a starting point
      personal_purposes: Personal purpose types defined by Normits


Household data
-------------------------------------------
UK household data in :class:`caf.base.DVector` format. Singular DVectors are required for each of the data inputs.
No specific segmentation is required, since the data is aggregated to the number of household per zone.
Occupied dwellings is required and unoccupied dwellings is optional. 
If both are given the number of dwellings used is the sum of both datasets, if unoccupied is not given, the occupied data is used as is.

The zone correspondence path should point to a CSV, which contains zone correspondence from the DVector's zoning to the model zoning,
see :ref:`Zone Correspondences` for information on the format of the CSV.


Employment Data
---------------
UK employment data in :class:`caf.base.DVector` format. A single DVector is required for the data input.
The DVector must be segmented by 'sic_1_digit', any other segments will be aggregated.
The zone correspondence path should point to a csv in caf.space format which contains zone correspondence from the DVector's zoning to the model zoning.


Warehouse Data
--------------

Warehouse floorspace area data is used for calculating trip ends for the
delivery and commute segments. The warehouse floorspace data used by
Transport for the North is aggregated from Ordnance Survey's Address
Base Premium and Master map data, the methodology for which is outlined
in the Local Freight Tool - Warehouse Data technical note [1]_.

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

   +-----------------------+------------------+---------------------------+
   | Column Name           | Data Type        | Description               |
   +=======================+==================+===========================+
   | LSOA11CD              | Text             | LSOA zone ID.             |
   +-----------------------+------------------+---------------------------+
   | area                  | Real             | Total warehouse           |
   |                       |                  | floorspace for the LSOA   |
   |                       |                  | (:math:`m^2`).            |
   +-----------------------+------------------+---------------------------+

**Note: any missing LSOAs are assumed to have zero floorspace.**\ \*

LGV Parameters Spreadsheet
--------------------------

This input should be an Excel spreadsheet containing a variety of sheets
with different parameters for the LGV model. Each of the required sheets
in this input file are discussed in the following sections.

Parameters
~~~~~~~~~~

The sheet named “Parameters” should contain two columns with the headers
“Parameter” and “Value”. The following table gives the names of the
parameters and a description of what value should be provided.

.. table:: Required parameters for the LGV model, parameters must be
   labelled exactly as given.

   +-------------+------+------------------------------------------------+
   | Parameter   | Data | Description                                    |
   |             | Type |                                                |
   +=============+======+================================================+
   | LGV growth  | Real | A factor to increase the LGV trips from the    |
   |             |      | van survey year to the model year              |
   +-------------+------+------------------------------------------------+
   | Average new | Real | The average new house size in :math:`m^2`      |
   | house size  |      |                                                |
   +-------------+------+------------------------------------------------+
   | Scotland    | Real | The proportion of SOC821 occupations in the    |
   | S           | (0 - | SOC82 segment                                  |
   | OC821/SOC82 | 1)   |                                                |
   +-------------+------+------------------------------------------------+
   | Model Year  | Int  | The model year e.g. 2018                       |
   |             | eger |                                                |
   +-------------+------+------------------------------------------------+

Commute Trips by Main Usage
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named “Commute trips by main usage” should contain the annual
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

   +--------+----------+--------------------------------------------------+
   | Column | Data     | Description                                      |
   | Name   | Type     |                                                  |
   +========+==========+==================================================+
   | Main   | Character| Usage code for each of the types listed above    |
   | usage  | (1)      |                                                  |
   +--------+----------+--------------------------------------------------+
   | Trips  | Real     | The annual number of commuting LGV trips for     |
   |        |          | that usage type                                  |
   +--------+----------+--------------------------------------------------+

Commute Trips by Land Use
~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named “Commute trips by land use” should contain the annual
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

The sheet named “Annual Service Trips” should contain the annual number
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

The sheet name “Delivery Segment Parameters” contains various mandatory
parameters, listed in the table below. The sheet should have the column
headers “Parameter” and “Value” on the first row.

.. table:: Required parameters for the delivery segment sheet,
   parameters should be named exactly as written.

   +-----------+-----------+---------------------------------------------------+
   | Parameter | Data Type | Description                                       |
   +===========+===========+===================================================+
   | Annual    | Integer   | The total annual trip productions for the         |
   | Trip      |           | delivery parcel stem segment from the DfT van     |
   | Pr        |           | survey, for the **base year**.                    |
   | oductions |           |                                                   |
   | - Parcel  |           |                                                   |
   | Stem      |           |                                                   |
   +-----------+-----------+---------------------------------------------------+
   | Annual    | Integer   | The total annual trips for the delivery parcel    |
   | Trips -   |           | bush segment from the DfT van survey, for the     |
   | Parcel    |           | **base year**.                                    |
   | Bush      |           |                                                   |
   +-----------+-----------+---------------------------------------------------+
   | Annual    | Integer   | The total annual trips for the delivery grocery   |
   | Trips -   |           | bush segment from the DfT van survey, for the     |
   | Grocery   |           | **base year**.                                    |
   | Bush      |           |                                                   |
   +-----------+-----------+---------------------------------------------------+
   | Delivery  | Real (>0) | Growth factor to apply to the annual delivery     |
   | Growth    |           | trips to factor to forecast year.                 |
   | Factor    |           |                                                   |
   +-----------+-----------+---------------------------------------------------+
   | B2C vs    | Real (>0) | The ratio of business-to-customer vs              |
   | B2B       |           | business-to-business delivery trips               |
   | Weighting |           |                                                   |
   +-----------+-----------+---------------------------------------------------+
   | Depots    | Comma -   | List of all zones in areas that aren't covered by |
   | Infill    | seperated | the warehouse dataset (e.g. Scotland), these      |
   | Zones     | list      | zones will have depots allocated based on number  |
   |           |           | of households.                                    |
   +-----------+-----------+---------------------------------------------------+

Commute Warehouse Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The sheet named “Commute Warehouse Parameters” should contain all the
parameters for the warehouse input calculations, including the weighting
factors and infilling parameters. The table below describes all the
required values and their use, the different weighting factors
correspond to the input files described in `Warehouse
Data <#warehouse-data>`__).

.. table:: Description of the commute warehouse parameters

   +-----------------------+--------------------------------+-------------+
   | Parameter             | Data Type                      | Description |
   +=======================+================================+=============+
   | Weighting - High      | Number                         | Factor to   |
   |                       |                                | apply to    |
   |                       |                                | the high    |
   |                       |                                | relevance   |
   |                       |                                | warehouse   |
   |                       |                                | floorspace  |
   |                       |                                | input.      |
   +-----------------------+--------------------------------+-------------+
   | Weighting - Medium    | Number                         | Factor to   |
   |                       |                                | apply to    |
   |                       |                                | the medium  |
   |                       |                                | relevance   |
   |                       |                                | warehouse   |
   |                       |                                | floorspace  |
   |                       |                                | input.      |
   +-----------------------+--------------------------------+-------------+
   | Weighting - Low       | Number                         | Factor to   |
   |                       |                                | apply to    |
   |                       |                                | the low     |
   |                       |                                | relevance   |
   |                       |                                | warehouse   |
   |                       |                                | floorspace  |
   |                       |                                | input.      |
   +-----------------------+--------------------------------+-------------+
   | Model Zone Infill     | Comma-separated list           | List of     |
   |                       |                                | model zones |
   |                       |                                | in commute  |
   |                       |                                | warehouse   |
   |                       |                                | data which  |
   |                       |                                | should be   |
   |                       |                                | infilled.   |
   +-----------------------+--------------------------------+-------------+
   | Zone Infill Method    | Text (from options below)      | Method for  |
   |                       |                                | infilling   |
   |                       |                                | model       |
   |                       |                                | zones.      |
   +-----------------------+--------------------------------+-------------+

Zone infill method calculates an infill value after all the warehouse
data has been factored and combined and then infills any zones in the
“Model Zone Infill” list, which don't contain non-zero values already.
The following methods can be chosen for calculating the infill value:

-  min: minimum value from existing data (including zeros)
-  mean: mean value from existing data
-  median: median value from existing data
-  non_zero_min: minimum non-zero value from existing data
-  zero: infills zones with zero

Time Period Factors
~~~~~~~~~~~~~~~~~~~

The sheet named “Time Period Factors” should contain all the factors for
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

**Note:** *the time period factors are expected to convert from annual
trips to average daily time period, therefore each factor should be less
than, approximately, 1/365.*

.. table:: Required columns for the time period factors sheet.

   +-----------+------+------------------------------------------------------+
   | Column    | Data | Description                                          |
   | Names     | Type |                                                      |
   +===========+======+======================================================+
   | Time      | Text | The name of the time period, will be used for naming |
   | Period    |      | the outputs                                          |
   +-----------+------+------------------------------------------------------+
   | Service   | Real | The factor to multiply the annual matrix by to get   |
   |           |      | the average daily time period (e.g. AM) for this     |
   |           |      | segment                                              |
   +-----------+------+------------------------------------------------------+
   | Delivery  | Real | The factor to multiply the annual matrix by to get   |
   | Parcel    |      | the average daily time period (e.g. AM) for this     |
   | Stem      |      | segment                                              |
   +-----------+------+------------------------------------------------------+
   | Delivery  | Real | The factor to multiply the annual matrix by to get   |
   | Parcel    |      | the average daily time period (e.g. AM) for this     |
   | Bush      |      | segment                                              |
   +-----------+------+------------------------------------------------------+
   | Delivery  | Real | The factor to multiply the annual matrix by to get   |
   | Grocery   |      | the average daily time period (e.g. AM) for this     |
   |           |      | segment                                              |
   +-----------+------+------------------------------------------------------+
   | Commuting | Real | The factor to multiply the annual matrix by to get   |
   | Drivers   |      | the average daily time period (e.g. AM) for this     |
   |           |      | segment                                              |
   +-----------+------+------------------------------------------------------+
   | Commuting | Real | The factor to multiply the annual matrix by to get   |
   | Skilled   |      | the average daily time period (e.g. AM) for this     |
   | Trades    |      | segment                                              |
   +-----------+------+------------------------------------------------------+



Gravity Model Parameters (``gm_parameters``)
--------------------------------------------

The gravity model is ran separately for each van segment, therefore the parameters
should be specified separately for each. The segment names should be given exactly
as follows: 'service', 'delivery_parcel_stem', 'delivery_parcel_bush', 'delivery_grocery', 'commuting_drivers', 'commuting_skilled_trades'.

The following sections outline the parameters which should be defined for each segment.

Trip Length Distribution (``trip_length_distribution_path``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This should be a CSV containing the trip length distribution(s) (TLD) to use for
calibration. The CSV should contain the following columns, with names:

+--------------+--------+-----------------------------------------------+
| Column       | Data   | Description                                   |                                      
| Name         | Type   |                                               |
+==============+========+===============================================+
| area         | string | This labels which area the TLD belongs to.    |                                 
|              | or     | Area Ids should correspond to those in the    |
|              | int    | Category Zone Correspondence.                 |
+--------------+--------+-----------------------------------------------+
| from         | Real   | The lower bin edge for the TLD.               |
+--------------+--------+-----------------------------------------------+
| to           | Real   | The upper bin edge for the TLD.               |
+--------------+--------+-----------------------------------------------+
| av_distance  | Real   | The average distance travelled within that    |
|              |        | bin and area.                                 |
+--------------+--------+-----------------------------------------------+
| normalised   | Real   | The proportion of trips that fall within that |
|              |        | bin and area.                                 |
+--------------+--------+-----------------------------------------------+

.. note::
    If ``cat_zone_correspondance_path`` is not given, the CSV does not need to contain 
    the area column and the tool will perform a single TLD calibration.
    Alternatively, TLDs can be calibrated to separately for different zones.

Category-Zone correspondence (``cat_zone_correspondance_path``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The category-zone correspondence is an optional lookup which defines which model zones
are calibrated to each TLD provided. This is required when attempting to perform
multi-TLD gravity model calibration.

.. table:: Format of the category zone correspondence
+--------------+--------+-----------------------------------------------+
| Column       | Data   | Description                                   |                                      
| Name         | Type   |                                               |
+==============+========+===============================================+
| area         | string | This labels which category the Zone belongs   |
|              | or     | to. Ids should correspond to those in the     |
|              | int    | Trip Length Distribution.                     |
+--------------+--------+-----------------------------------------------+
| zone_id      | text   | Should contain the IDs of all zones in the    |  
|              | or     | mode zone system, without duplicates.         | 
|              | int    |                                               |
+--------------+--------+-----------------------------------------------+

Cost Function (``cost_function``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The cost function to use for the gravity model, either "log_normal" or "tanner".
If you don't know which to use, consult TAG or your nearest demand modelling
expert.

.. note::
    If using multi-TLD calibration all TLDs will use the same cost function,
    although different parameters can be defined for each (see
    :ref:`Cost Function params (cost_function_params)`).

Log Normal
**********

The log normal function is defined as:

.. math::

    f(C_{ij}) = \frac{1}{C_{ij} \cdot \sigma \cdot \sqrt{2\pi}}
    \cdot \exp\left(-\frac{(\ln C_{ij}-\mu)^2}{2\sigma^2}\right)

where:

- :math:`C_{ij}`: cost from i to j.
- :math:`\sigma, \mu`: calibration parameters.

Tanner
******

The tanner function is defined as:

.. math:: f(C_{ij}) = C_{ij}^\alpha \cdot \exp(\beta C_{ij})

where:

- :math:`C_{ij}`: cost from i to j.
- :math:`\alpha, \beta`: calibration parameters.


Cost Function params (``cost_function_params``)  
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  

The starting values for the cost function parameters to use when calibrating,  
or just the values to use if calibration is off. Both cost functions require  
two parameters (in a specific order):  

- Log normal: :math:`\mu` (mu), :math:`\sigma` (sigma) 
- Tanner: :math:`\alpha` (alpha), :math:`\beta` (beta)  

If a single pair of parameters is provided these will be used for all TLDs, 
alternatively separate parameters can be provided for each of the area IDs in :ref:`Category-Zone correspondence (cat_zone_correspondance_path)`.  

Calibrate
~~~~~~~~~

* True to calibrate the gravity model to the TLD(s).
* False to run the gravity model with given cost parameters.

Furness Jacobian
~~~~~~~~~~~~~~~~

Whether to furness the Jacobian matrix in the gravity model, see
`caf.distribute <https://cafdistribute.readthedocs.io/en/stable/>`_ for
the implementation details.

.. warning::
    Setting this to True may cause poor results for matrices that fail to converge,
    this a known issue for the "bush" matrices ("delivery grocery" and "delivery bush")
    which contain mostly intrazonal trips by definition. If you find poor results for
    these matrices, try setting furness jacobian to off.

Trip End Balancing regions (``tripend_balancing_regions_path``)
---------------------------------------------------------------

Optional CSV containing zone groups which the van trip ends will be balanced at.
The CSV should be in the same format as the
:ref:`Category-Zone correspondence (cat_zone_correspondance_path)`.

If this isn't given then the trip ends will be balanced at all zones, i.e. the
GB total trip ends.

Constructions (``constructions_path``)
----------------------------------

This should contains the dwelling and employment floorspace changes in the model zoning.

.. table:: Required columns in the Constructions CSV
+----------------------+--------+--------------------------------------------+
| Column               | Data   | Description                                |                                      
| Name                 | Type   |                                            |
+======================+========+============================================+
| zone                 | Text   | The model zoning IDs.                      |
|                      | or     |                                            |
|                      | int    |                                            |
+----------------------+--------+--------------------------------------------+
| additonal_dwellings  | Real   | The number of dwellings constructed in the | 
|                      |        | model year within the zone.                |
+----------------------+--------+--------------------------------------------+
| demolished_dwellings | Real   | The number of dwellings constructed in the |
|                      |        | model year within the zone.                |
+----------------------+--------+--------------------------------------------+
| buisness_floorspace  | Real   | The floorspace, in m^2, constructed in the |
|                      |        | model year, within the zone.               |
+----------------------+--------+--------------------------------------------+

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

   +-------------------------------------+------------+-----------------------+
   | Column Name                         | Data Type  | Description           |
   +=====================================+============+=======================+
   | 2011 super output area - lower      | Text       | LSOA name             |
   | layer                               |            |                       |
   +-------------------------------------+------------+-----------------------+
   | mnemonic                            | Text       | LSOA area code        |
   +-------------------------------------+------------+-----------------------+
   | All categories: Occupation          | Integer    | Total occupation      |
   +-------------------------------------+------------+-----------------------+
   | 51. Skilled agricultural and        | Integer    | Occupation numbers for|
   | related trades                      |            | this segment          |
   +-------------------------------------+------------+-----------------------+
   | 52. Skilled metal, electrical and   | Integer    | Occupation numbers for|
   | electronic trades                   |            | this segment          |
   +-------------------------------------+------------+-----------------------+
   | 53. Skilled construction and        | Integer    | Occupation numbers for|
   | building trades                     |            | this segment          |
   +-------------------------------------+------------+-----------------------+
   | 821. Road Transport Drivers         | Integer    | Occupation numbers for|
   |                                     |            | this segment          |
   +-------------------------------------+------------+-----------------------+
   

The QS606UK census table should contain the occupation data extracted
for Scotland only at datazone level and should be provided with the
units persons. The expected columns for this input are shown in the
table below.

.. table:: Required columns for the QS606UK occupation data CSV.

   +---------------------------------------+-----------+------------------------+
   | Column Name                           | Data Type | Description            |
   +=======================================+===========+========================+
   | 2011 scottish datazone                | Text      | Datazone name          |
   +---------------------------------------+-----------+------------------------+
   | mnemonic                              | Text      | Datazone area code     |
   +---------------------------------------+-----------+------------------------+
   | All categories: Occupation            | Integer   | Total occupation       |
   +---------------------------------------+-----------+------------------------+
   | 51. Skilled agricultural and related  | Integer   | Occupation numbers for |
   | trades                                |           | this segment           |
   +---------------------------------------+-----------+------------------------+
   | 52. Skilled metal, electrical and     | Integer   | Occupation numbers for |
   | electronic trades                     |           | this segment           |
   +---------------------------------------+-----------+------------------------+
   | 53. Skilled construction and building | Integer   | Occupation numbers for |
   | trades                                |           | this segment           |
   +---------------------------------------+-----------+------------------------+
   | 82. Transport and mobile machine      | Integer   | Occupation numbers for |
   | drivers and operatives                |           | this segment           |
   +---------------------------------------+-----------+------------------------+

Zone Correspondences
-------------------------

Zone correspondence CSVs are required for converting Warehouse 
and Occupation data from LSOA to the model zone system and annual matrices to a summary zone system.
The summary zone system can be chosen by the user to suit the specific situation. LSOA to model zones requires
 column names on the first row and three required columns, listed in the table below.

.. table:: Required columns for the LSOA zone correspondence CSV, column
   names are ignored the columns just need to be in the correct order.

   ====== ========= ===================================
   Column Data Type Description
   ====== ========= ===================================
   1      Text      Area code e.g. E01000001
   2      Integer   Corresponding model zone ID
   3      Real      Splitting factor for correspondence
   ====== ========= ===================================

The summary zone correspondence should be in `caf.space <https://cafspace.readthedocs.io/en/stable/>`_
format, containing the following columns:
   - {from_zoning}_id - the model zone ID
   - {to_zoning}_id - the summary zone ID
   - {from_zoning}_{to_zoning} - translation factor, best practice is to use aggragated zones 
      for the summary, so all of theses should be 1.

Zoning
------
This should be the name of the model zoning system, which should match that in the 
zone correspondence file.

Model zones
-----------

The model zones file should contain a *complete list of the zone IDs*.

.. table:: Required columns for the study area lookup CSV, column names
   must be exactly as listed any other columns are ignored.

   +--------+-------------+-----------------------------------------------+
   | Column | Data Type   | Description                                   |
   | Name   |             |                                               |
   +========+=============+===============================================+
   | zone   | Integer     | The model zone number                         |
   +--------+-------------+-----------------------------------------------+

Cost Matrix
-----------

Matrix CSV containing the cost values for all zones in the model, the
units of the costs should be the same as the units in the `LGV Trip
Distributions Spreadsheet <#lgv-trip-distributions-spreadsheet>`__. The
CSV file should be in square matrix format where the first column and
row contains all the zone numbers, an example of a three by three matrix
with the same costs for all zones is shown below.

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

The calibration matrix should be a CSV in the same format as `Cost
Matrix <#cost-matrix>`__. This matrix is used during the gravity model
process to adjust the impact of trips between certain zone pairs and
should have positive values around 0 - 2. The `Gravity
Model <#gravity-model>`__ section outlines the methodology where this
input is used.

Output Folder
-------------

The parent directory where all the outputs will be saved. A new
sub-folder will be created with the name convention “LGV Model Outputs -
{date} {time}” (e.g. “LGV Model Outputs - 2021-08-05 19.15.32”) will be
created to store the outputs for a single run of the LGV model.

.. [1]
   Local Freight Tool - Warehouse Data Technical Note (April - May 2023)
