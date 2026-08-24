Quick Start
===========

CAF.van is provided as a Python package and a command-line utility.
The command-line utility can be used to run the complete caf.van process, without using Python directly,
and should be used for most cases. For more bespoke use-case caf.van functionality can be called 
directly from Python. See :ref:`usage` for details.

CAF.van can be installed from pip, conda-forge or **pipx
(when using as a command-line utility).**


Pip
---
Installing through pip is easy and can be done in one command:
``pip install caf.van``

conda-forge
-----------
Installing through conda-forge is easy and can be done in one command:
``conda install caf.van -c conda-forge``

Usage
-----
The tool should be run from the command-line and a configuration (YAML) file to pass the inputs.
The command to call the tool is:
``python -m caf.van -c path/to/config.yaml``

CAF.van provides a command-line interface (CLI) for running the van model. The
below details the basic usage and arguments for running from the command line,
the details for the inputs and methodology are outlined in :ref:`tool usage`.

CLI
^^^

.. argparse::
    :module: caf.van
    :func: lgv_arg_parser
    :nosubcommands:

Python
^^^^^^

When using CAF.van functionality within Python:

.. code:: python

    import caf.van as cvan

The :ref:`user guide` contains :ref:`tutorials` and :ref:`code examples`, which
explain available functionality. For a detailed look at the
package API see :ref:`API Reference`.
