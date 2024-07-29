"""
    Main module for running the LGV model.
"""

##### IMPORTS #####


# Local Imports
from caf.van.lgv_inputs import LGVInputPaths, write_example_config
from caf.van.lgv_model import lgv_arg_parser, main

##### MAIN #####

# Check if commandline arguments are given
parser = lgv_arg_parser()
args = parser.parse_args()

if args.example:
    write_example_config(args.config_file)

elif args.config_file is not None:
    # Run the LGV model without displaying the UI if config is given
    input_paths = LGVInputPaths.load_yaml(args.config_file)
    main(input_paths)

else:
    parser.print_help()
