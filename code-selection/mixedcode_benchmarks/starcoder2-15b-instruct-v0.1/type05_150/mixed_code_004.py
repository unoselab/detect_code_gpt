def hwc_mixed_004_01(axis_tag, user_loc):
    """Go from Glyphs UI strings to user space location.
    Returns None if the string is invalid.

    >>> user_loc_string_to_value('wght', 'ExtraLight')
    200
    >>> user_loc_string_to_value('wdth', 'SemiCondensed')
    87.5
    >>> user_loc_string_to_value('wdth', 'Clearly Not From Glyphs UI')
    """
    if axis_tag == "wght":
        try:
            value = _nospace_lookup(WEIGHT_CODES, user_loc)
        except KeyError:
            return None
        return class_to_value("wght", value)
    elif axis_tag == "wdth":
        try:
            value = _nospace_lookup(WIDTH_CODES, user_loc)
        except KeyError:
            return None
        return class_to_value("wdth", value)

    # Currently this function should only be called with a width or weight
    raise NotImplementedError 

def hwc_mixed_004_02(self, frame):
        """ Called by dispatch function to check wether debugger must stop at
        this frame.
        Note that we test 'step into' first to give a chance to 'stepOver' in
        case user click on 'stepInto' on a 'no call' line.
        """
        # TODO: Optimization => defines a set of modules / names where _tracer
        # is never registered. This will replace skip
        #if self.skip and self.is_skipped_module(frame.f_globals.get('__name__')):
        #    return False

        # step into
        if self.frame_calling and self.frame_calling==frame.f_back:
            return True
        # step over
        if frame==self.frame_stop:  # frame cannot be null
            return True
        # step out
        if frame==self.frame_return:  # frame cannot be null
            return True
        # suspend
        if self.frame_suspend:
            return True

        return False 

def agc_mixed_004_03(devname, **kwargs):
    """
    Changes the offload parameters and other features of the specified network device

    CLI Example:

    .. code-block:: bash

        salt '*' ethtool.set_offload <devname> tcp_segmentation_offload=on
    """

    for key, value in kwargs.items():
        if key == "tcp_segmentation_offload":
            if value == "on":
                print(f"Enabling TCP segmentation offload on {devname}")
            elif value == "off":
                print(f"Disabling TCP segmentation offload on {devname}")
            else:
                raise ValueError(f"Invalid value for {key}: {value}")
        else:
            raise ValueError(f"Unsupported parameter: {key}") 

def hwc_mixed_004_04(self, until=None):
        """Sets the DHW off until a given time, or permanently."""
        if until is None:
            data = {"Mode": "PermanentOverride",
                    "State": "Off",
                    "UntilTime": None}
        else:
            data = {"Mode": "TemporaryOverride",
                    "State": "Off",
                    "UntilTime": until.strftime('%Y-%m-%dT%H:%M:%SZ')}

        self._set_dhw(data) 

def agc_mixed_004_05(self, cond, value, other=None, subset=None, **kwargs):
        """
        Apply a function elementwise, updating the HTML
        representation with a style which is selected in
        accordance with the return value of a function.

        .. versionadded:: 0.21.0

        Parameters
        ----------
        cond : callable
            ``cond`` should take a scalar and return a boolean
        value : str
            applied when ``cond`` returns true
        other : str
            applied when ``cond`` returns false
        subset : IndexSlice
            a valid indexer to limit ``data`` to *before* applying the
            function. Consider using a pandas.IndexSlice
        kwargs : dict
            pass along to ``cond``

        Returns
        -------
        self : Styler

        See Also
        --------
        Styler.applymap
        """

        if subset is not None:
            self.data = self.data.loc[subset]
        for row_idx, row in self.data.iterrows():
            for col_idx, val in row.iteritems():
                if cond(val, **kwargs):
                    self.data.loc[row_idx, col_idx] = value
                else:
                    self.data.loc[row_idx, col_idx] = other
        return self 

def agc_mixed_004_06(attr_ids, node_ids, **kwargs):
    """
        For a given attribute or set of attributes, return  all the resources and
        resource scenarios in the network
    """
    if not attr_ids:
        raise ValueError("attr_ids cannot be empty")
    if not node_ids:
        raise ValueError("node_ids cannot be empty")
    if not isinstance(attr_ids, list):
        raise TypeError("attr_ids must be a list")
    if not isinstance(node_ids, list):
        raise TypeError("node_ids must be a list")
    resources = []
    resource_scenarios = []
    for attr_id in attr_ids:
        for node_id in node_ids:
            resources.append(f"Resource {attr_id} {node_id}")
            resource_scenarios.append(f"Resource scenario {attr_id} {node_id}")

    return resources, resource_scenarios
