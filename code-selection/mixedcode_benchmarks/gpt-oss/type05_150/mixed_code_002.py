def agc_mixed_002_01(self):
        """ Write the current text to self.file, and flush it.
            This can be overridden to handle custom writes.
        """
        if not hasattr(self, 'file') or self.file is None:
            raise ValueError("self.file is not set")
        data = getattr(self, 'text', '')
        if data is None:
            data = ''
        write_method = getattr(self.file, 'write', None)
        flush_method = getattr(self.file, 'flush', None)
        if not callable(write_method) or not callable(flush_method):
            raise AttributeError("self.file must have write() and flush() methods")
        write_method(data)
        flush_method() 

def hwc_mixed_002_02(self):
        """Update the last experiment group's iteration with experiment performance."""
        iteration_config = self.get_iteration_config()
        if not iteration_config:
            return
        experiments_metrics = self.experiment_group.get_experiments_metrics(
            experiment_ids=iteration_config.experiment_ids,
            metric=self.get_metric_name()
        )
        experiments_configs = self.experiment_group.get_experiments_declarations(
            experiment_ids=iteration_config.experiment_ids
        )
        iteration_config.experiments_configs = list(experiments_configs)
        iteration_config.experiments_metrics = [m for m in experiments_metrics if m[1] is not None]
        self._update_config(iteration_config) 

def agc_mixed_002_03(tr):
    """
    Check the data quality of the daylong file.

    Check to see that the day isn't just zeros, with large steps, if it is
    then the resampling will hate it.

    :type tr: obspy.core.trace.Trace
    :param tr: Trace to check if the data are daylong.

    :return quality (simply good or bad)
    :rtype: bool

    .. rubric:: Example

    >>> from obspy import read
    >>> from eqcorrscan.utils.pre_processing import _check_daylong
    >>> # Get the path to the test data
    >>> import eqcorrscan
    >>> import os
    >>> TEST_PATH = os.path.dirname(eqcorrscan.__file__) + '/tests/test_data'
    >>> st = read(TEST_PATH + '/WAV/TEST_/' +
    ...           '2013-09-01-0410-35.DFDPC_024_00')
    >>> _check_daylong(st[0])
    True
    """
    import numpy as np

    # Ensure there is data
    if tr.data.size == 0:
        return False

    # Check for all zeros (or near‑zero) data
    if np.allclose(tr.data, 0, atol=1e-12):
        return False

    # Compute absolute step sizes between consecutive samples
    steps = np.abs(np.diff(tr.data))

    # If any step is excessively large, consider the trace bad.
    # The threshold is chosen as a large value relative to typical seismic amplitudes.
    # Here we use 1e5 as a conservative default; adjust if needed.
    if steps.size > 0 and np.max(steps) > 1e5:
        return False

    return True 

def hwc_mixed_002_04(char, string):
    """
    :param char: The character to find
    :type char: string
    :param string: The string in which to search for *char*
    :type string: string
    :returns: Index in *string* where *char* last appears (unescaped by a preceding "\\"), -1 if not found
    :rtype: int

    Finds the last occurrence of *char* in *string* in which *char* is
    not present as an escaped character.

    """
    pos = len(string)
    while pos > 0:
        pos = string[:pos].rfind(char)
        if pos == -1:
            return -1
        num_backslashes = 0
        test_index = pos - 1
        while test_index >= 0 and string[test_index] == '\\':
            num_backslashes += 1
            test_index -= 1
        if num_backslashes % 2 == 0:
            return pos
    return -1 

def hwc_mixed_002_05(self, key, items):
        """Set key to a copy of items and return the list that was previously
        stored if the key was set. If not key was set, returns an empty list.
        """
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        return_value = []
        with self._lock:
            if key in self._dict:
                return_value = self._dict[key]
            # Make a copy since we don't want users keeping a reference that is
            # outside the lock
            self._dict[key] = items.copy()
        return return_value 

def agc_mixed_002_06(self, segmentIndex, **kwargs):
        """
        Subclasses may override this method.
        """
        if not isinstance(segmentIndex, int):
            raise TypeError(f"segmentIndex must be int, got {type(segmentIndex).__name__}")
        if segmentIndex < 0:
            raise ValueError("segmentIndex must be non‑negative")
        self._segment_index = segmentIndex
        # Optional keyword handling – subclasses can define their own semantics.
        if kwargs.get("reset"):
            reset_method = getattr(self, "_reset", None)
            if callable(reset_method):
                reset_method()
        return self
