Methodology
===========

.. todo::
   Review methodology and update to align with current tool.

The van model is split into six model segments for different types of
van trips, these are the following:

-  Service
-  Delivery Grocery
-  Delivery Parcel Bush
-  Delivery Parcel Stem
-  Commute Drivers
-  Commute Skilled Trades

The van model methodology is split into three sections, only the first
of which varies between model segments, these are as follows:

-  Trip end generation;
-  Gravity model / annual trip matrix creation; and
-  Conversion to time period matrices.

The following sections will discuss each of the three parts of the
methodology in turn, with flowcharts detailing the main components of
each.

Trip End Generation
-------------------

The trip end generation varies for each of the model segments in order
to account for the types of trips that are being modelled. The trip end
generation is done as productions and attractions for each of the
segments except the delivery bush trips where they instead have origin
and destination trip ends.

The trip end generation uses various inputs from the DfT van survey and
census data tables, these are all outlined in the :ref:`van model inputs`
section. This section will discuss the methodologies for the three main
segments (which each contain sub-segments that make up the six total
van model segments).

Service Trip Ends
~~~~~~~~~~~~~~~~~

The trip ends for the service segment are calculated by using employment
and household projections data to distribute the total annual service
trips (from the DfT van survey) to the model zone system. The trip ends
are distributed separately for the sub-segments of Residential, Office
and All Other Employment before being combined together into a single
set of service productions and attractions. The flowchart below outlines
the service trip ends methodology.

.. figure:: ../_static/images/LGV_methodology-Servicing.drawio.svg
   :alt: Van service productions and attractions trip ends methodology -
      flowchart

   Van service productions and attractions trip ends methodology

Delivery Trip Ends
~~~~~~~~~~~~~~~~~~

The trip ends for the delivery segment are split into three different
sub-segments, detailed below:

-  Parcel stem: These are delivery trips which originate at the depots
   and end at the first drop-off location. These trips would likely be
   the longest single trip in a delivery round and there would be a
   corresponding return trip back to the depot to pickup more packages.
-  Parcel bush: These are the delivery trips which go between various
   drop-off locations and would tend to be lots of shorter trips.
-  Grocery (bush): These would encompass the trips from the supermarket
   to the customers but would likely all relatively short as the
   supermarkets are closer to the customers than delivery depots are.
   There will be less total grocery trips in a single round but more
   rounds per day as each delivery will be larger than parcel
   deliveries.

The parcel stem trips are calculated as productions and attractions,
whereas both the bush types are origin / destination trip ends. The
flowchart below outlines the methodology for calculating the trip ends
for all three types of delivery trip.

.. todo::
   Update flowchart to show trips are factored using delivery growth factor

.. figure:: ../_static/images/LGV_methodology-Delivery.drawio.svg
   :alt: Van delivery trip ends methodology - flowchart

   Van delivery trip ends methodology

Commuting Trip Ends
~~~~~~~~~~~~~~~~~~~

The trip ends for the commuting segment are split into two sub-segments,
detailed below:

-  Skilled trades: These are the commuting trips which represent skilled
   workers who commute by LGV due to need to carry tools and equipment.
   These workers may be commuting to a construction site or to a
   residential / employment building to provide some service.
-  Drivers: These are the LGV commuting trips which represent resident
   drivers.

Both commuting segments are calculated as productions and attractions,
these methodologies have been split into two flowcharts below, one for
each type of trip end.

.. todo::
   Update flowchart to show trips are factored using growth factor

.. figure:: ../_static/images/LGV_methodology-Commuting-Productions.drawio.svg
   :alt: Van commuting productions trip ends methodology - flowchart

   Van commuting productions trip ends methodology

.. figure:: ../_static/images/LGV_methodology-Commuting-Attractions.drawio.svg
   :alt: Van commuting attractions trip ends methodology - flowchart

   Van commuting attractions trip ends methodology

Gravity Model
-------------

The package utilises [caf.distribute](https://cafdistribute.readthedocs.io/en/stable/) multi-TLD
gravity model for calibrating and running the gravity model. The gravity model distributes trips
based on the purposes' calculated trip ends and inputted trip-length distributions (TLD).
This is achieved by fitting the cost function parameters to match the target TLD and Furnessing
then achieved distribution to match the trip ends. The multi-TLD gravity allows for different areas
to have their own TLDs, for more information on this process please see
:class:`caf.distribute.gravity_model.multi_area.MultiAreaGravityModelCalibrator`.

Time Period Conversion
----------------------

The final process of the LGV model is the conversion from annual to time
period specific trip matrices. The conversion is done by factoring the
annual matrices (for each model segment) by the period factor provided
for each of the given time periods. The time period factors should be
provided separately to respect the different time profiles for each of
the model segments, the factors are provided in the :ref:`van parameters spreadsheet`.
