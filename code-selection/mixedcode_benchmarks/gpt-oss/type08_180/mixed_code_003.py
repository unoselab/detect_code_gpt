def agc_mixed_003_01(pkg):
    """ checks if a particular rpm package is installed """

    import subprocess
    import shutil

    if not isinstance(pkg, str) or not pkg:
        raise ValueError("Package name must be a non‑empty string")
    rpm_cmd = shutil.which("rpm")
    if rpm_cmd is None:
        # rpm command not available; cannot determine installation status
        return False
    try:
        result = subprocess.run(
            [rpm_cmd, "-q", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False 

def agc_mixed_003_02(self, match=None, count=None):
        """Take a pattern expected by the redis `scan` command and iter on all matching keys

        Parameters
        ----------
        match: str
            The pattern of keys to look for
        count: int, default to None (redis uses 10)
            Hint for redis about the number of expected result

        Yields
        -------
        str
            All keys found by the scan, one by one. A key can be returned multiple times, it's
            related to the way the SCAN command works in redis.

        """
        cursor = 0
        scan_kwargs = {}
        if match is not None:
            scan_kwargs["match"] = match
        if count is not None:
            scan_kwargs["count"] = count

        while True:
            cursor, keys = self.client.scan(cursor, **scan_kwargs)
            for key in keys:
                yield key.decode() if isinstance(key, (bytes, bytearray)) else key
            if cursor == 0 or cursor == b'0':
                break 

def agc_mixed_003_03(self, trigger_ids=[]):
        """
        Enable triggers.

        :param trigger_ids: List of trigger definition ids to enable
        """
        if not trigger_ids:
            # Enable all known triggers
            ids_to_enable = list(self.triggers.keys())
        else:
            ids_to_enable = trigger_ids

        # Validate trigger IDs
        unknown = [tid for tid in ids_to_enable if tid not in self.triggers]
        if unknown:
            raise ValueError(f"Unknown trigger IDs: {unknown}")

        # Enable the triggers
        for tid in ids_to_enable:
            self.triggers[tid]['enabled'] = True

        # Return the list of enabled trigger IDs
        return ids_to_enable 

def hwc_mixed_003_04(self, instance):
        """ Returns a dict of the operations needed to update this object.
            See :func:`Document.get_dirty_ops` for more details."""
        obj_value = instance._values[self._name]
        if not obj_value.set:
            return {}

        if not obj_value.dirty and self.__type.config_extra_fields != 'ignore':
            return {}

        ops = obj_value.value.get_dirty_ops()

        ret = {}
        for op, values in ops.items():
            ret[op] = {}
            for key, value in values.items():
                name = '%s.%s' % (self._name, key)
                ret[op][name] = value
        return ret 

def hwc_mixed_003_05(graph):
    """
    Do a topological sort on the dependency graph dict.
    """
    while graph:
        # Find all items without a parent
        leftmost = [l for l, s in graph.items() if not s]
        if not leftmost:
            raise ValueError('Dependency cycle detected! %s' % graph)
        # If there is more than one, sort them for predictable order
        leftmost.sort()
        for result in leftmost:
            # Yield and remove them from the graph
            yield result
            graph.pop(result)
            for bset in graph.values():
                bset.discard(result) 

def hwc_mixed_003_06(self, lexer):
        """Build saveframe loop.

        :param lexer: instance of lexical analyzer.
        :type lexer: :func:`~nmrstarlib.bmrblex.bmrblex`
        :return: Fields and values of the loop.
        :rtype: :py:class:`tuple`
        """
        fields = []
        values = []

        token = next(lexer)
        while token[0] == u"_":
            fields.append(token[1:])
            token = next(lexer)

        while token != u"stop_":
            values.append(token)
            token = next(lexer)

        assert float(len(values) / len(fields)).is_integer(), \
            "Error in loop construction: number of fields must be equal to number of values."

        values = [OrderedDict(zip(fields, values[i:i + len(fields)])) for i in range(0, len(values), len(fields))]
        return fields, values
