def agc_mixed_003_01(obj):
    """
    Generator that iterates the template and its ancestors.
    The order is from most specialized (furthest descendant) to
    most general (furthest ancestor).

    obj can be either:
        1. Mako Template object
        2. Mako `self` object (available within a rendering template)
    """
    if isinstance(obj, Template):
        yield obj
        for parent in obj.parents:
            for ancestor in template_inheritance(parent):
                yield ancestor
    elif isinstance(obj, Context):
        yield obj.template
        for parent in obj.template.parents:
            for ancestor in template_inheritance(parent):
                yield ancestor
    else:
        raise TypeError("obj must be either a Mako Template or a Mako Context") 

def hwc_mixed_003_02(api_method, org_id, query, first_page_size=100):
    """
    Takes an API method handler ``dxpy.api.org_find...`` and calls it with
    *org_id* and *query*, then wraps a generator around its output. Used by
    :meth:`org_find_members` and :meth:`org_find_projects` below.

    :param first_page_size: The number of results that the initial API call will return.
    :type first_page_size: int

    """
    if "limit" not in query:
        query["limit"] = min(first_page_size, 1000)

    while True:
        resp = api_method(org_id, query)
        for result in resp["results"]:
            yield result

        # set up next query
        if resp["next"] is not None:
            query["starting"] = resp["next"]
            query["limit"] = min(query["limit"] * 2, 1000)
        else:
            break 

def hwc_mixed_003_03(nc):
    """
    Returns a list of all variables matching definitions for latitude

    :param netcdf4.dataset nc: an open netcdf dataset object
    """
    latitude_variables = []
    # standard_name takes precedence
    for variable in nc.get_variables_by_attributes(standard_name="latitude"):
        latitude_variables.append(variable.name)

    # Then axis
    for variable in nc.get_variables_by_attributes(axis='Y'):
        if variable.name not in latitude_variables:
            latitude_variables.append(variable.name)

    check_fn = partial(attr_membership, value_set=VALID_LAT_UNITS,
                           modifier_fn=lambda s: s.lower())
    for variable in nc.get_variables_by_attributes(units=check_fn):
        if variable.name not in latitude_variables:
            latitude_variables.append(variable.name)

    return latitude_variables 

def hwc_mixed_003_04(self, metric, value, timestamp=None, tags={}):
        """Send given metric and (int or float) value to Graphite host.
        Performs send on background thread if "interval" was specified when
        creating this Sender.

        If a "tags" dict is specified, send the tags to the Graphite host along with the metric.
        """
        if timestamp is None:
            timestamp = time.time()
        message = self.build_message(metric, value, timestamp, tags)

        if self.interval is None:
            self.send_socket(message)
        else:
            try:
                self._queue.put_nowait(message)
            except queue.Full:
                logger.error('queue full when sending {!r}'.format(message)) 

def agc_mixed_003_05(self):
        """Check the input data types of the state

        Checks all input data ports if the handed data is not of the specified type and generate an error logger message
        with details of the found type conflict.
        """
        for port in self.input_ports:
            if not isinstance(port.data, type(self.input_ports[0].data)):
                self.logger.error(
                    "Input port {} has data type {} but the state has data type {}.".format(
                        port.name, type(port.data), type(self.input_ports[0].data)
                    )
                ) 

def agc_mixed_003_06(s, encoding=None, errors='strict', normalize=False):
    """
    Given str, bytes, bytearray, or unicode (py2), return str
    """
    if isinstance(s, bytes):
        if encoding is None:
            encoding = 'utf-8'
        return s.decode(encoding, errors)
    elif isinstance(s, bytearray):
        if encoding is None:
            encoding = 'utf-8'
        return s.decode(encoding, errors)
    elif isinstance(s, str):
        return s
    elif isinstance(s, unicode):
        return s.encode('utf-8')
    else:
        raise TypeError('to_str() argument must be str, bytes, bytearray, or unicode, not %s' % type(s).__name__)
