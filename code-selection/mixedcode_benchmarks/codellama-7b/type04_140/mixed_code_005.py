def agc_mixed_005_01():
    """
    :return:
        A unicode string of the system abi. Will be something like: "cp27m",
        "cp33m", etc.
    """

    import sys
    import platform

    if sys.platform == "win32":
        return "win32"

    if platform.python_implementation() == "PyPy":
        return "pypy"

    if platform.python_implementation() == "Jython":
        return "jython"

    if platform.python_implementation() == "IronPython":
        return "ironpython"

    if platform.python_implementation() == "CPython":
        return "cp%s%s" % (
            sys.version_info.major,
            sys.version_info.minor,
        )

    raise RuntimeError("Unknown Python implementation: %s" % platform.python_implementation()) 

def hwc_mixed_005_02(self, name, offset=0):
        """
        Checks a module name eg. some i3status modules cannot have an instance
        name.
        """
        if name in ["general"]:
            return
        split_name = name.split()
        if len(split_name) > 1 and split_name[0] in I3S_SINGLE_NAMES:
            self.current_token -= len(split_name) - 1 - offset
            self.error("Invalid name cannot have 2 tokens")
        if len(split_name) > 2:
            self.current_token -= len(split_name) - 2 - offset
            self.error("Invalid name cannot have more than 2 tokens") 

def agc_mixed_005_03(address: str) -> str:
    """
    Quote a subset of the email addresses defined by RFC 821.

    Should be able to handle anything email.utils.parseaddr can handle.
    """
    if not address:
        return ""
    if address[0] == '"':
        return address
    if address.find('@') == -1:
        return address
    if address.find('"') == -1:
        return address
    if address.find('(') == -1:
        return address
    if address.find(')') == -1:
        return address
    if address.find('\\') == -1:
        return address
    if address.find(' ') == -1:
        return address
    return '"' + address + '"' 

def hwc_mixed_005_04(self):
        """Creates a new database"""
        self.db_attrs = self.consul.create_db(
                self.instance_name,
                self.instance_type,
                self.admin_username,
                self.admin_password,
                db_name=self.db_name,
                storage_size_gb=self.storage_size,
                timeout_s=self.launch_timeout_s,
                ) 

def hwc_mixed_005_05(self, pydict, recovery_name=True):
        """Convert naive get response data to human readable field name format.

        using raw data format.
        """
        new_dict = {"id": pydict["id"]}
        for field in self:
            raw_key = "%s_raw" % field.key
            if raw_key in pydict:
                if recovery_name:
                    new_dict[field.name] = pydict[raw_key]
                else:
                    new_dict[field.key] = pydict[raw_key]
        return new_dict 

def agc_mixed_005_06(arg):
    """
    to_auto_download_state(arg) attempts to coerce the given argument into a valid auto-downloading
      instruction. Essentially, if arg is "on", "yes", "true", "1", True, or 1, then True is
      returned; if arg is "structure" then "structure" is returned; otherwise False is returned.
    """
    if isinstance(arg, bool):
        return arg
    elif isinstance(arg, int):
        return bool(arg)
    elif isinstance(arg, str):
        arg = arg.lower()
        if arg in ("on", "yes", "true", "1"):
            return True
        elif arg == "structure":
            return "structure"
        else:
            return False
    else:
        return False
