def agc_mixed_004_01() -> Union[None, Dict[str, str]]:
    """ Try and load an index file from the various places it might exist.

    If the legacy file cannot be found or cannot be parsed, return None.

    This method should only be called on a robot.
    """
    legacy_index_path = os.path.join(os.path.dirname(__file__), "index.json")
    if os.path.exists(legacy_index_path):
        with open(legacy_index_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass

    # Next, try and load the index from the robot's config.
    if "index" in config.config:
        return config.config["index"]

    # Finally, try and load the index from the robot's config.
    if "index" in config.config:
        return config.config["index"]

    return None 

def hwc_mixed_004_02(self, ascii_listing):
        """
        parse the given ASCII BASIC listing.
        Return a ParsedBASIC() instance.
        """
        self.parsed_lines = ParsedBASIC()
        for match in self.regex_line_no.finditer(ascii_listing):
            log.info("_" * 79)
            log.info("parse line >>>%r<<<", match.group())
            line_no = int(match.group("no"))
            line_content = match.group("content")

            self.line_data = []
            self._parse_code(line_content)
            log.info("*** line %s result: %r", line_no, self.line_data)

            self.parsed_lines[line_no] = self.line_data

        return self.parsed_lines 

def agc_mixed_004_03(self, visibility, mode="add"):
        """Return the AR fields with the current visibility
        """
        if visibility == "all":
            return self.fields
        elif visibility == "none":
            return []
        elif visibility == "add":
            return self.fields.filter(add_to_ar=True)
        elif visibility == "edit":
            return self.fields.filter(edit_in_ar=True)
        elif visibility == "view":
            return self.fields.filter(view_in_ar=True)
        else:
            return [] 

def agc_mixed_004_04(cmd, no_newline_regexp="Progess", sudo=False):
    """stream a command (yield) back to the user, as each line is available.

       # Example usage:
       results = []
       for line in stream_command(cmd):
           print(line, end="")
           results.append(line)

       Parameters
       ==========
       cmd: the command to send, should be a list for subprocess
       no_newline_regexp: the regular expression to determine skipping a
                          newline. Defaults to finding Progress

    """
    if sudo:
        cmd = ["sudo"] + cmd
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        line = p.stdout.readline()
        if line:
            line = line.decode("utf-8")
            if no_newline_regexp and re.search(no_newline_regexp, line):
                continue
            yield line
        else:
            break
    p.wait()
    if p.returncode:
        raise subprocess.CalledProcessError(p.returncode, cmd) 

def hwc_mixed_004_05():
    """
    Checks that *xgboost* is available.
    """
    try:
        import xgboost
    except ImportError:
        return False
    from xgboost.core import _LIB
    try:
        _LIB.XGBoosterDumpModelEx
    except AttributeError:
        # The version is not recent enough even though it is version 0.6.
        # You need to install xgboost from github and not from pypi.
        return False
    from xgboost import __version__
    vers = LooseVersion(__version__)
    allowed = LooseVersion('0.7')
    if vers < allowed:
        warnings.warn('The converter works for xgboost >= 0.7. Earlier versions might not.')
    return True 

def hwc_mixed_004_06(self, goal):
        """Get the shortest way between two nodes of the graph

        Args:
            goal (str): Name of the targeted node
        Return:
            list of Node
        """
        if goal == self.name:
            return [self]

        if goal not in self.routes:
            raise ValueError("Unknown '{0}'".format(goal))

        obj = self
        path = [obj]
        while True:
            obj = obj.routes[goal].direction
            path.append(obj)
            if obj.name == goal:
                break
        return path
