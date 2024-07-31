"""
    Main module for running the LGV model.
"""

##### IMPORTS #####

# Third Party
from caf.toolkit import LogHelper, ToolDetails

# Local Imports
import caf.van
from caf.van import lgv_inputs, lgv_model

##### MAIN #####


def main():
    # Check if commandline arguments are given
    parser = lgv_model.lgv_arg_parser()
    args = parser.parse_args()

    if args.example:
        lgv_inputs.write_example_config(args.config_file)

    elif args.config_file is not None:
        # Run the LGV model without displaying the UI if config is given
        input_paths = lgv_inputs.LGVInputPaths.load_yaml(args.config_file)

        details = ToolDetails(__package__, caf.van.__version__)
        log_file = input_paths.output_folder / "van.log"

        with LogHelper(__package__, details, log_file):
            lgv_model.main(input_paths)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
