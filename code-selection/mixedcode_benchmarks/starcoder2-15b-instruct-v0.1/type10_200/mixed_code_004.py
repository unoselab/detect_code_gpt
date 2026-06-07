def agc_mixed_004_01(self, userid, **kwargs):
        """
        Find a set of NameID's that matches the search criteria.

        :param userid: User id
        :param kwargs: The search filter a set of attribute/value pairs
        :return: a list of NameID instances
        """
        nameids = []
        for nameid in self.nameids:
            if nameid.userid == userid:
                match = True
                for key, value in kwargs.items():
                    if getattr(nameid, key)!= value:
                        match = False
                        break
                if match:
                    nameids.append(nameid)
        return nameids 

def agc_mixed_004_02(plan_details, to_log=True):
    """Display current and proposed changes in
    topic-partition to replica layout over brokers.
    """
    current_assignment = plan_details["current_assignment"]
    proposed_assignment = plan_details["proposed_assignment"]
    for topic, partitions in current_assignment.items():
        for partition, replicas in partitions.items():
            current_replicas = replicas
            proposed_replicas = proposed_assignment[topic][partition]
            if current_replicas!= proposed_replicas:
                print(f"Topic: {topic}, Partition: {partition}")
                print(f"Current replicas: {current_replicas}")
                print(f"Proposed replicas: {proposed_replicas}")
                if to_log:
                    log_message = f"Topic: {topic}, Partition: {partition}, Current replicas: {current_replicas}, Proposed replicas: {proposed_replicas}"
                    log(log_message) 

def hwc_mixed_004_03(snaps, refresh=False):
    """Install OpenStack snaps from channel and with mode

    @param snaps: Dictionary of snaps with channels and modes of the form:
        {'snap_name': {'channel': 'snap_channel',
                       'mode': 'snap_mode'}}
        Where channel is a snapstore channel and mode is --classic, --devmode
        or --jailmode.
    @param post_snap_install: Callback function to run after snaps have been
    installed
    """

    def _ensure_flag(flag):
        if flag.startswith('--'):
            return flag
        return '--{}'.format(flag)

    if refresh:
        for snap in snaps.keys():
            snap_refresh(snap,
                         _ensure_flag(snaps[snap]['channel']),
                         _ensure_flag(snaps[snap]['mode']))
    else:
        for snap in snaps.keys():
            snap_install(snap,
                         _ensure_flag(snaps[snap]['channel']),
                         _ensure_flag(snaps[snap]['mode'])) 

def hwc_mixed_004_04(self, size=1, param=None):
        """Gives a set of random values drawn from this distribution.

        Parameters
        ----------
        size : {1, int}
            The number of values to generate; default is 1.
        param : {None, string}
            If provided, will just return values for the given parameter.
            Otherwise, returns random values for each parameter.

        Returns
        -------
        structured array
            The random values in a numpy structured array. If a param was
            specified, the array will only have an element corresponding to the
            given parameter. Otherwise, the array will have an element for each
            parameter in self's params.
        """
        if param is not None:
            dtype = [(param, float)]
        else:
            dtype = [(p, float) for p in self.params]
        arr = numpy.zeros(size, dtype=dtype)
        for (p,_) in dtype:
            offset = numpy.power(self._bounds[p][0], self.dim)
            factor = numpy.power(self._bounds[p][1], self.dim) - \
                                      numpy.power(self._bounds[p][0], self.dim)
            arr[p] = numpy.random.uniform(0.0, 1.0, size=size)
            arr[p] = numpy.power(factor * arr[p] + offset, 1.0 / self.dim)
        return arr 

def agc_mixed_004_05(self, state, **kwargs):
        """
        Generally starts containers that are not running. Attached containers are skipped unless they are initial.
        Attached containers are also prepared with permissions. Where applicable, exec commands are run in started
        instance containers.

        :param state: Configuration state.
        :type state: dockermap.map.state.ConfigState
        :param kwargs: Additional keyword arguments.
        :return: Actions on the client, map, and configurations.
        :rtype: list[dockermap.map.action.ItemAction]
        """
        actions = []
        for item in state.items:
            if item.is_container:
                if item.is_running:
                    continue
                actions.append(ItemAction(item, Action.START))
            elif item.is_attached:
                if item.is_initial:
                    continue
                actions.append(ItemAction(item, Action.ATTACH))
            if item.is_exec:
                actions.append(ItemAction(item, Action.EXEC))
        return actions 

def hwc_mixed_004_06(val, valtype, floatfmt, missingval="", has_invisible=True):
    """Format a value accoding to its type.

    Unicode is supported:

    >>> hrow = ['\u0431\u0443\u043a\u0432\u0430', '\u0446\u0438\u0444\u0440\u0430'] ; \
        tbl = [['\u0430\u0437', 2], ['\u0431\u0443\u043a\u0438', 4]] ; \
        good_result = '\\u0431\\u0443\\u043a\\u0432\\u0430      \\u0446\\u0438\\u0444\\u0440\\u0430\\n-------  -------\\n\\u0430\\u0437             2\\n\\u0431\\u0443\\u043a\\u0438           4' ; \
        tabulate(tbl, headers=hrow) == good_result
    True

    """
    if val is None:
        return missingval

    if valtype in [int, _long_type, _text_type]:
        return "{0}".format(val)
    elif valtype is _binary_type:
        try:
            return _text_type(val, "ascii")
        except TypeError:
            return _text_type(val)
    elif valtype is float:
        is_a_colored_number = has_invisible and isinstance(val, (_text_type, _binary_type))
        if is_a_colored_number:
            raw_val = _strip_invisible(val)
            formatted_val = format(float(raw_val), floatfmt)
            return val.replace(raw_val, formatted_val)
        else:
            return format(float(val), floatfmt)
    else:
        return "{0}".format(val)
