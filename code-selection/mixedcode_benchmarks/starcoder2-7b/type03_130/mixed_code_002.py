def agc_mixed_002_01(k, options, field=None, isBytes=False):
    """ Given k kilobytes, report back the correct format as string.
    """
    if k == 0:
        return "0"
    if isBytes:
        k = k / 1024.0
    if k < 1024:
        return "%.1f KB" % k
    elif k < 1024 * 1024:
        return "%.1f MB" % (k / 1024.0)
    elif k < 1024 * 1024 * 1024:
        return "%.1f GB" % (k / (1024.0 * 1024.0))
    else:
        return "%.1f TB" % (k / (1024.0 * 1024.0 * 1024.0)) 

def hwc_mixed_002_02(filenameOrSamfile, indent=0):
    """
    List SAM/BAM file reference names and lengths.

    @param filenameOrSamfile: Either a C{str} SAM/BAM file name or an
        instance of C{pysam.AlignmentFile}.
    @param indent: An C{int} number of spaces to indent each line.
    @return: A C{str} describing known reference names and their lengths.
    """
    indent = ' ' * indent

    def _references(sam):
        result = []
        for i in range(sam.nreferences):
            result.append('%s%s (length %d)' % (
                indent, sam.get_reference_name(i), sam.lengths[i]))
        return '\n'.join(result)

    if isinstance(filenameOrSamfile, six.string_types):
        with samfile(filenameOrSamfile) as sam:
            return _references(sam)
    else:
        return _references(sam) 

def agc_mixed_002_03(self, connection, event):
        """
        event.arguments[0] == "@" for secret channels,
                          "*" for private channels,
                          "=" for others (public channels)
        event.arguments[1] == channel
        event.arguments[2] == nick list
        """

        if event.arguments[0] == "@":
            self.log.debug("Secret channel %s joined by %s", event.arguments[1], event.arguments[2])
            self.channels[event.arguments[1]].add_user(event.arguments[2])
        elif event.arguments[0] == "*":
            self.log.debug("Private channel %s joined by %s", event.arguments[1], event.arguments[2])
            self.channels[event.arguments[1]].add_user(event.arguments[2])
        elif event.arguments[0] == "=":
            self.log.debug("Public channel %s joined by %s", event.arguments[1], event.arguments[2])
            self.channels[event.arguments[1]].add_user(event.arguments[2]) 

def agc_mixed_002_04(self, indexes, as_list=False):
        """
        Given indexes will return a sub-set of the Series. This method will direct to the specific methods
        based on what types are passed in for the indexes. The type of the return is determined by the
        types of the parameters.

        :param indexes: index value, list of index values, or a list of booleans.
        :param as_list: if True then return the values as a list, if False return a Series.
        :return: either Series, list, or single value. The return is a shallow copy
        """
        if isinstance(indexes, list):
            if isinstance(indexes[0], bool):
                return self._get_bool_list(indexes, as_list)
            else:
                return self._get_index_list(indexes, as_list)
        elif isinstance(indexes, int):
            return self._get_index(indexes, as_list)
        else:
            raise TypeError("indexes must be a list of booleans or integers") 

def hwc_mixed_002_05(self, name, type_p, max_bytes_per_sec):
        """Creates a new bandwidth group.

        in name of type str
            Name of the bandwidth group.

        in type_p of type :class:`BandwidthGroupType`
            The type of the bandwidth group (network or disk).

        in max_bytes_per_sec of type int
            The maximum number of bytes which can be transfered by all
            entities attached to this group during one second.

        """
        if not isinstance(name, basestring):
            raise TypeError("name can only be an instance of type basestring")
        if not isinstance(type_p, BandwidthGroupType):
            raise TypeError("type_p can only be an instance of type BandwidthGroupType")
        if not isinstance(max_bytes_per_sec, baseinteger):
            raise TypeError("max_bytes_per_sec can only be an instance of type baseinteger")
        self._call("createBandwidthGroup",
                     in_p=[name, type_p, max_bytes_per_sec]) 

def hwc_mixed_002_06(self, interface_id, address, value_key, value):
        """If a device emits some sort event, we will handle it here."""
        LOG.debug("RPCFunctions.event: interface_id = %s, address = %s, value_key = %s, value = %s" % (
            interface_id, address, value_key.upper(), str(value)))
        self.devices_all[interface_id.split(
            '-')[-1]][address].event(interface_id, value_key.upper(), value)
        if self.eventcallback:
            self.eventcallback(interface_id=interface_id, address=address,
                               value_key=value_key.upper(), value=value)
        return True
