from parse_it.command_line_args.command_line_args import *
from parse_it.envvars.envvars import *
from parse_it.file.yaml import *
from parse_it.file.ini import *
from parse_it.file.json import *
from parse_it.file.hcl import *
from parse_it.file.toml import *
from parse_it.file.xml import *
from parse_it.type_estimate.type_estimate import *
from parse_it.file.file_reader import *

VALID_FILE_TYPE_EXTENSIONS = [
    "json",
    "yaml",
    "yml",
    "toml",
    "tml",
    "hcl",
    "tf",
    "conf",
    "cfg",
    "ini",
    "xml"
]


class ParseIt:

    def __init__(self, config_type_priority=None, global_default_value=None, type_estimate=True, recurse=True,
                 force_envvars_uppercase=True, config_folder_location=None, envvar_prefix=None):
        """configures the object which is used to query all types of configuration inputs available and prioritize them
                based on your needs

                    Arguments:
                        config_type_priority -- a list of file types extensions your willing to accept, list order
                            dictates priority of said file types, default list order is as follow:
                                [ "cli_args", "envvars", "json", "yaml", "yml", "toml", "tml", "hcl", "tf", "conf",
                                "cfg", "ini", "xml" ]
                            in the case of multiple files of same type they are all read and the first one that has the
                                needed key is the one used.
                            if no value is returned then the default_value declared at the read_configuration_variable
                                will be used and if that is not configured then the global_default_value will be used
                        global_default_value -- defaults to None, see config_type_priority for it's use
                        type_estimate -- if set to True (True by default) will try to automatically figure out the type
                            of the returned value on it's own, useful for envvars & ini type files which always return a
                            string otherwise
                        recurse -- True by default, if set to True will also look in all subfolders
                        force_envvars_uppercase -- if set to True (which is the default) will force all envvars keys to
                            be UPPERCASE
                        envvar_prefix -- will add a prefix for all envvars if set
        """

        if envvar_prefix is None:
            self.envvar_prefix = ""
        else:
            self.envvar_prefix = envvar_prefix
        self.global_default_value = global_default_value
        self.type_estimate = type_estimate
        self.force_envvars_uppercase = force_envvars_uppercase
        if config_type_priority is None:
            self.config_type_priority = [
                "cli_args",
                "env_vars",
                "json",
                "yaml",
                "yml",
                "toml",
                "tml",
                "hcl",
                "tf",
                "conf",
                "cfg",
                "ini",
                "xml"
            ]
        else:
            self.config_type_priority = config_type_priority
        if config_folder_location is None:
            self.config_folder_location = os.getcwd()
        else:
            self.config_folder_location = config_folder_location
        file_types_in_folder_list = []
        for config_type in self.config_type_priority:
            if config_type in VALID_FILE_TYPE_EXTENSIONS:
                file_types_in_folder_list.append(config_type)
        self.config_files_dict = file_types_in_folder(self.config_folder_location, file_types_in_folder_list,
                                                      recurse=recurse)

    def read_configuration_variable(self, config_name, default_value=None, required=False):
        """reads a single key of the configuration and returns the first value of it found based on the priority of each
                config file option given in the __init__ of the class

                    Arguments:
                        config_name -- the configuration key name you want to get the value of
                        default_value -- defaults to None, see config_type_priority in class init for it's use
                        required -- defaults to False, if set to True will ignore default_value & global_default_value
                            and will raise an ValueError if the configuration is not configured in any of the config
                            files/envvars/cli args
                    Returns:
                        config_value -- the value of the configuration requested
        """

        # we start with both key not found and the value being None
        config_value = None
        config_key_found = False

        # we now loop over all the permitted types of where the config key might be and break on the first one found
        # after setting config_key_found to True and config_value to the value found
        for config_type in self.config_type_priority:
            if config_type == "cli_args":
                config_key_found = command_line_arg_defined(config_name)
                if config_key_found is True:
                    config_value = read_command_line_arg(config_name)
                    break
            elif config_type == "envvars" or config_type == "env_vars":
                config_key_found = envvar_defined(self.envvar_prefix + config_name,
                                                  force_uppercase=self.force_envvars_uppercase)
                config_value = read_envvar(self.envvar_prefix + config_name,
                                           force_uppercase=self.force_envvars_uppercase)
                if config_key_found is True:
                    break
            # will loop over all files of each type until all files of all types are searched, first time the key is
            # found will break outside of both loops
            elif config_type in VALID_FILE_TYPE_EXTENSIONS:
                for config_file in self.config_files_dict[config_type]:
                    file_dict = self._parse_file_per_type(config_type, os.path.join(self.config_folder_location,
                                                                                    config_file))
                    config_key_found, config_value = self._check_config_in_dict(config_name, file_dict)
                    if config_key_found is True:
                        break
                if config_key_found is True:
                    break
            else:
                raise ValueError

        # raise error if the key is required and not found in any of the config files, envvar or cli args
        if config_key_found is False and required is True:
            raise ValueError

        # if key is not required but still wasn't found take it from the key default value or failing that from the
        # global default value
        if config_key_found is False:
            if default_value is not None:
                config_value = default_value
            else:
                config_value = self.global_default_value

        # if type estimation is True try to guess the type of the value
        if self.type_estimate is True:
            config_value = estimate_type(config_value)
        return config_value

    @staticmethod
    def _check_config_in_dict(config_key, config_dict):
        """internal function which checks if the key is in a given dict

            Arguments:
                config_key -- the configuration key name you want to check if it exists in the dict
                config_dict -- the dict you want to check if the is included in
            Returns:
                config_found -- True if the key is in the dict, false otherwise
                config_value -- the value of the configuration requested, returns None if the key is not part of the
                    the dict
        """
        if config_key in config_dict:
            config_value = config_dict[config_key]
            config_found = True
        else:
            config_value = None
            config_found = False
        return config_found, config_value

    @staticmethod
    def _parse_file_per_type(config_file_type, config_file_location):
        """internal function which parses a file to a dict when given the file format type and it's location

            Arguments:
                config_file_type -- the type of the config file
                config_file_location -- the location of the config file
            Returns:
                file_dict -- a parsed dict of the config file data
        """
        if config_file_type == "json":
            file_dict = parse_json_file(config_file_location)
        elif config_file_type == "yaml" or config_file_type == "yml":
            file_dict = parse_yaml_file(config_file_location)
        elif config_file_type == "toml" or config_file_type == "tml":
            file_dict = parse_toml_file(config_file_location)
        elif config_file_type == "conf" or config_file_type == "cfg" or config_file_type == "ini":
            file_dict = parse_ini_file(config_file_location)
        elif config_file_type == "hcl" or config_file_type == "tf":
            file_dict = parse_hcl_file(config_file_location)
        elif config_file_type == "xml":
            file_dict = parse_xml_file(config_file_location)
        else:
            raise ValueError
        return file_dict
