def hwc_mixed_004_01(self, find_url, **attributes):
        """
            :param find_url: URL of the find api
            :type find_url: string
            :return: The Response returned by requests including the list of documents based on find_url
            :rtype: Response object
        """
        req = self.url + find_url

        # Add range and sort parameters
        params = {
            "range": attributes.get("range", "all"),
            "sort": attributes.get("sort", [])
        }

        # Add body
        data = {
            "query": attributes.get("query", {})
        }

        try:
            return requests.post(req, params=params, json=data, proxies=self.proxies, auth=self.auth, verify=self.cert)
        except requests.exceptions.RequestException as e:
            raise TheHiveException("Error: {}".format(e)) 

def hwc_mixed_004_02(self):
        """
        Get all date about the current execution frame

        :return: current frame data
        :rtype: dict
        :raises AttributeError: if the debugger does hold any execution frame.
        :raises IOError: if source code for the current execution frame is not accessible.
        """
        filename = self.curframe.f_code.co_filename
        lines, start_line = inspect.findsource(self.curframe)
        if sys.version_info[0] == 2:
            lines = [line.decode('utf-8') for line in lines]
        return {
            'dirname': os.path.dirname(os.path.abspath(filename)) + os.path.sep,
            'filename': os.path.basename(filename),
            'file_listing': ''.join(lines),
            'current_line': self.curframe.f_lineno,
            'breakpoints': self.get_file_breaks(filename),
            'globals': self.get_globals(),
            'locals': self.get_locals()
        } 

def agc_mixed_004_03(append=None, prepend=None, replace=None, on=os):
    """Update the PATH environment variable.

    Can append, prepend, or replace the path.  Each of these expects a string
    or a list of strings (for multiple path elements) and can operate on remote
    connections that offer an @environ@ attribute using the @on@ argument.
    """

    if on is None:
        on = os
    if on.environ is None:
        return
    if append is not None:
        if isinstance(append, str):
            append = [append]
        on.environ['PATH'] = os.pathsep.join(append + on.environ['PATH'].split(os.pathsep))
    if prepend is not None:
        if isinstance(prepend, str):
            prepend = [prepend]
        on.environ['PATH'] = os.pathsep.join(on.environ['PATH'].split(os.pathsep) + prepend)
    if replace is not None:
        if isinstance(replace, str):
            replace = [replace]
        on.environ['PATH'] = os.pathsep.join(replace) 

def agc_mixed_004_04(self):
        """
        Check if the dashboard cookie should exist through bikasetup
        configuration.

        If it should exist but doesn't exist yet, the function creates it
        with all values as default.
        If it should exist and already exists, it returns the value.
        Otherwise, the function returns None.

        :return: a dictionary of strings
        """
        # Getting cookie
        if self.dashboard_cookie_exists:
            return self.dashboard_cookie
        else:
            self.dashboard_cookie = {}
            self.dashboard_cookie['name'] = self.dashboard_cookie_name
            self.dashboard_cookie['value'] = self.dashboard_cookie_value
            self.dashboard_cookie['domain'] = self.dashboard_cookie_domain
            self.dashboard_cookie['path'] = self.dashboard_cookie_path
            self.dashboard_cookie['expires'] = self.dashboard_cookie_expires
            self.dashboard_cookie['secure'] = self.dashboard_cookie_secure
            self.dashboard_cookie['httponly'] = self.dashboard_cookie_httponly
            self.dashboard_cookie['session'] = self.dashboard_cookie_session
            return self.dashboard_cookie 

def hwc_mixed_004_05(self, attr_dict, attr):
        # Note: Code & comments unchanged from DirectedHypergraph
        """Combines attr_dict and attr dictionaries, by updating attr_dict
            with attr.

        :param attr_dict: dictionary of attributes of the node.
        :param attr: keyword arguments of attributes of the node;
                    attr's values will override attr_dict's values
                    if both are provided.
        :returns: dict -- single dictionary of [combined] attributes.
        :raises: AttributeError -- attr_dict argument must be a dictionary.

        """
        # If no attribute dict was passed, treat the keyword
        # arguments as the dict
        if attr_dict is None:
            attr_dict = attr
        # Otherwise, combine the passed attribute dict with
        # the keyword arguments
        else:
            try:
                attr_dict.update(attr)
            except AttributeError:
                raise AttributeError("attr_dict argument \
                                     must be a dictionary.")
        return attr_dict 

def agc_mixed_004_06(self, event):
        """Update rotation parmeters based on mouse movement"""
        if event.button == 1:
            self.rotation_x += event.delta[1] * 0.2
            self.rotation_y += event.delta[0] * 0.2
        elif event.button == 2:
            self.rotation_x += event.delta[1] * 0.05
            self.rotation_y += event.delta[0] * 0.05
        elif event.button == 3:
            self.rotation_x += event.delta[1] * 0.05
            self.rotation_y += event.delta[0] * 0.05
        else:
            return
        self.rotation_x = np.clip(self.rotation_x, -90, 90)
