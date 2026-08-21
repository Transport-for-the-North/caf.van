Quick Start
===========

.. todo::
    Write brief description about the possible ways for using the tool e.g. CLI, GUI and
    importing in Python.

*CAF.van is provided as a Python package and a command-line utility.
The command-line utility aims to make some of the commonly used functionality 
available without needing to use Python code, see :ref:`usage` for details.*

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

Pipx
----

`Pipx <https://pipx.pypa.io/stable/>`__ is the recommended way to use caf.van as a utility.
It handles installing the tool in its own container, and makes it easy to access from a terminal.

First install pipx into your default Python environment using pip or conda, see
`Pipx's installation instructions <https://pipx.pypa.io/stable/installation/>`__ for more details.

Once pipx is installed and setup caf.toolkit can be installed using ``pipx install caf.van``,
this should make it available in command-line anywhere using ``caf.van ...``.

.. _start-usage:

Usage
-----

CAF.van provides a command-line interface (CLI) for running the van model. The
below details the basic usage and arguments for running from the command line,
the details for the inputs and methodology are outlined in :ref:`tool usage`.

CLI
^^^

.. argparse::
    :module: caf.van.lgv_model
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
