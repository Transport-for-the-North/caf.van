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
    """Main function for the package."""
    # Check if commandline arguments are given
    parser = lgv_model.lgv_arg_parser()
    args = parser.parse_args()

    if args.example:
        lgv_inputs.LGVInputPaths.write_example(lgv_inputs.EXAMPLE_CONFIG_NAME)

    elif args.config_file is not None:
        # Run the LGV model without displaying the UI if config is given
        input_paths = lgv_inputs.LGVInputPaths.load_yaml(args.config_file)

        details = ToolDetails(__package__, caf.van.__version__)
        log_file = input_paths.model_output_folder / "van.log"

        with LogHelper("caf", details, log_file=log_file):
            lgv_model.main(input_paths)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
