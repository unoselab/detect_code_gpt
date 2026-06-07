def agc_mixed_004_01(time_series, width, step, order='F'):
    """
    Segments univariate time series with sliding window

    Parameters
    ----------
    time_series : array like shape [n_samples]
        time series or sequence
    width : int > 0
        segment width in samples
    step : int > 0
        stepsize for sliding in samples

    Returns
    -------
    w : array like shape [n_segments, width]
        resampled time series segments
    """
    import numpy as np

    ts = np.asarray(time_series)
    if not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")
    if not isinstance(step, int) or step <= 0:
        raise ValueError("step must be a positive integer")
    n = ts.shape[0]
    if width > n:
        return np.empty((0, width), dtype=ts.dtype, order=order)

    # Use sliding_window_view if available, otherwise fallback to stride tricks
    try:
        from numpy.lib.stride_tricks import sliding_window_view
        windows = sliding_window_view(ts, width)[::step]
    except Exception:
        # Manual stride trick
        stride = ts.strides[0]
        shape = ((n - width) // step + 1, width)
        strides = (step * stride, stride) 

def agc_mixed_004_02(bus_name, cur_station=None):
    """Get real time routine.

    TODO support fuzzy matching.

    :param bus_name: the routine name of the bus.
    :param cur_station: current station, deaults to starting station
                        of the routine.
    """
    _ROUTES = {
        "RouteA": ["Station1", "Station2", "Station3", "Station4"],
        "RouteB": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "RouteC": ["North", "East", "South", "West"],
    }

    # Look up the routine; raise if unknown.
    if bus_name not in _ROUTES:
        raise ValueError(f"Unknown bus routine: {bus_name!r}")

    stations = _ROUTES[bus_name]

    # If no current station is supplied, start from the first station.
    if cur_station is None:
        return stations.copy()

    # Find the index of the current station; raise if not present.
    try:
        idx = stations.index(cur_station)
    except ValueError as exc:
        raise ValueError(f"Station {cur_station!r} not found in routine {bus_name!r}") from exc

    # Return the remaining routine from the current station onward.
    return stations[idx:].copy() 

def hwc_mixed_004_03(
      self, number_of_consumed_events, number_of_produced_events):
    """Updates the number of events.

    Args:
      number_of_consumed_events (int): total number of events consumed by
          the process.
      number_of_produced_events (int): total number of events produced by
          the process.

    Returns:
      bool: True if either number of events has increased.

    Raises:
      ValueError: if the consumed or produced number of events is smaller
          than the value of the previous update.
    """
    consumed_events_delta = 0
    if number_of_consumed_events is not None:
      if number_of_consumed_events < self.number_of_consumed_events:
        raise ValueError(
            'Number of consumed events smaller than previous update.')

      consumed_events_delta = (
          number_of_consumed_events - self.number_of_consumed_events)

      self.number_of_consumed_events = number_of_consumed_events
      self.number_of_consumed_events_delta = consumed_events_delta

    produced_events_delta = 0
    if number_of_produced_events is not None:
      if number_of_produced_events < self.number_of_produced_events:
        raise ValueError(
            'Number of produced events smaller than previous update.')

      produced_events_delta = (
          number_of_produced_events - self.number_of_produced_events)

      self.number_of_produced_events = number_of_produced_events
      self.number_of_produced_events_delta = produced_events_delta

    return consumed_events_delta > 0 or produced_events_delta > 0 

def hwc_mixed_004_04(modname, parent=None):
    """
    print(ut.import_star_execstr('opengm.inference'))
    """
    from utool import util_str
    module_vars = import_star(modname, parent=parent)
    fromlist_str = ', '.join(sorted(module_vars.keys()))
    fromimport_prefix = 'from {modname} import ('.format(modname=modname)

    newline_prefix = (' ' * len(fromimport_prefix))
    if fromlist_str:
        rawstr = fromimport_prefix + fromlist_str + ',)'
    else:
        rawstr = ''
    textwidth = 79 - 4
    fromimport_str = util_str.pack_into(rawstr, textwidth=textwidth,
                                        newline_prefix=newline_prefix,
                                        break_words=False)

    # fromimport_str = ut.autopep8_format(fromimport_str, ignore={})
    return fromimport_str 

def agc_mixed_004_05(self, amplification_group):
        """
        Creates the numpy array tables from the hdf5 tables
        """
        # Determine shape of the tables
        import numpy as np
        import h5py

        tables = {}

        def _traverse(group, prefix=""):
            for name, obj in group.items():
                full_name = f"{prefix}{name}"
                if isinstance(obj, h5py.Dataset):
                    tables[full_name] = np.array(obj)
                elif isinstance(obj, h5py.Group):
                    _traverse(obj, prefix=full_name + "/")

        _traverse(amplification_group)
        self.tables = tables
        return tables 

def hwc_mixed_004_06(self, force=False):
        """
        Ensure appropriate connections.

        """
        now = time.perf_counter()
        if now < self.nextCheck and not force:
            return False
        self.nextCheck = now + (self.config.RETRY_TIMEOUT_NOT_RESTRICTED
                                if self.isKeySharing
                                else self.config.RETRY_TIMEOUT_RESTRICTED)
        missing = self.connectToMissing()
        self.retryDisconnected(exclude=missing)
        logger.trace("{} next check for retries in {:.2f} seconds"
                     .format(self, self.nextCheck - now))
        return True
