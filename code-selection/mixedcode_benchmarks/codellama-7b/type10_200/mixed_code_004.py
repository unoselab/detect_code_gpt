def hwc_mixed_004_01(self, template, use_format=False):
        """Compile replacements."""

        is_replace = _is_replace(template)
        is_string = isinstance(template, (str, bytes))
        if is_replace and use_format != template.use_format:
            raise ValueError("Compiled replace cannot be a format object!")
        if is_replace or (is_string and self.auto_compile):
            return self.compile(template, (FORMAT if use_format and not is_replace else 0))
        elif is_string and use_format:
            # Reject an attempt to run format replace when auto-compiling
            # of template strings has been disabled and we are using a
            # template string.
            raise AttributeError('Format replaces cannot be called without compiling replace template!')
        else:
            return template 

def agc_mixed_004_02(dist, _, value):
    # type: (setuptools.dist.Distribution, str, bool) -> None
    """Add autodetected commands as entry points.

    Args:
        dist: The distutils Distribution object for the project being
            installed.
        _: The keyword used in the setup function. Unused.
        value: The value set to the keyword in the setup function. If the value
            is not True, this function will do nothing.
    """
    if not isinstance(value, bool):
        raise TypeError(
            "The keyword 'setup_keyword' must be set to True or False, not {!r}".format(value)
        )

    if value:
        # Add the autodetected commands as entry points.
        for command in get_commands():
            dist.entry_points.append(
                setuptools.dist.Distribution.EntryPoint(
                    "console_scripts",
                    "{} = {}".format(command.name, command.module_name),
                    dist=dist.get_name(),
                )
            ) 

def hwc_mixed_004_03(template):
    """A generator which yields Token instances"""
    upto = 0
    lineno = 0

    for m in tag_re.finditer(template):

        start, end = m.span()
        lineno = template.count('\n', 0, start) + 1  # Humans count from 1
        # If there's a gap between our start and the end of the last match,
        # there's a Text node between.
        if upto < start:
            yield Token(TokenType.text, template[upto:start], lineno)
        upto = end

        mode = m.lastgroup
        content = m.group(mode)
        yield Token(TokenType[mode], content, lineno)

    # if the last match ended before the end of the source, we have a tail Text
    # node.
    if upto < len(template):
        yield Token(TokenType.text, template[upto:], lineno) 

def hwc_mixed_004_04(entry):
        """
        Transform a line from a hosts file into an instance of HostsEntry
        :param entry: A line from the hosts file
        :return: An instance of HostsEntry
        """
        line_parts = entry.strip().split()
        if is_ipv4(line_parts[0]) and valid_hostnames(line_parts[1:]):
            return HostsEntry(entry_type='ipv4',
                              address=line_parts[0],
                              names=line_parts[1:])
        elif is_ipv6(line_parts[0]) and valid_hostnames(line_parts[1:]):
            return HostsEntry(entry_type='ipv6',
                              address=line_parts[0],
                              names=line_parts[1:])
        else:
            return False 

def agc_mixed_004_05(self, enabled):
        """Update the UI when the user toggles the bookmarks radiobutton.

        :param enabled: The status of the radiobutton.
        :type enabled: bool
        """
        if enabled:
            self.hazard_exposure_bookmark_button.setEnabled(True)
            self.hazard_exposure_bookmark_button.setChecked(True)
            self.hazard_exposure_bookmark_button.setText("Remove Bookmark")
            self.hazard_exposure_bookmark_button.setIcon(
                self.style().standardIcon(QStyle.SP_DialogDiscardButton)
            )
            self.hazard_exposure_bookmark_button.setToolTip("Remove Bookmark")
        else:
            self.hazard_exposure_bookmark_button.setEnabled(True)
            self.hazard_exposure_bookmark_button.setChecked(False)
            self.hazard_exposure_bookmark_button.setText("Add Bookmark")
            self.hazard_exposure_bookmark_button.setIcon(
                self.style().standardIcon(QStyle.SP_DialogApplyButton)
            )
            self.hazard_exposure_bookmark_button.setToolTip("Add Bookmark") 

def agc_mixed_004_06(self, url, method="GET", params=dict(), headers=dict()):
        """
        Request a API endpoint at ``url`` with ``params`` being either the
        POST or GET data.
        """
        if method == "GET":
            url += "?" + urlencode(params)
            params = None
        elif method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            raise ValueError("Invalid method: %s" % method)

        if self.debug:
            print("Request: %s %s" % (method, url))
            print("Params: %s" % params)
            print("Headers: %s" % headers)

        response = requests.request(method, url, params=params, headers=headers)

        if self.debug:
            print("Response: %s" % response.text)

        return response
