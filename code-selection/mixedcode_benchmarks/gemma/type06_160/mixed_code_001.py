def agc_mixed_001_01(name, encoding=None, errors='strict'):
    """Returns a system stream for text processing.  This usually returns
    a wrapped stream around a binary stream returned from
    :func:`get_binary_stream` but it also can take shortcuts on Python 3
    for already correctly configured streams.

    :param name: the name of the stream to open.  Valid names are ``'stdin'``,
                 ``'stdout'`` and ``'stderr'``
    :param encoding: overrides the detected default encoding.
    :param errors: overrides the default error mode.
    """
    import sys
    import io

    streams = {
        'stdin': sys.stdin,
        'stdout': sys.stdout,
        'stderr': sys.stderr
    }

    if name not in streams:
        raise ValueError(f"Invalid stream name: {name}")

    stream = streams[name]

    if hasattr(stream, 'reconfigure'):
        if encoding is not None or errors is not None:
            stream.reconfigure(encoding=encoding, errors=errors)
        return stream

    # Fallback for environments where reconfigure is unavailable
    # Wrap the underlying binary buffer
    binary_stream = getattr(stream, 'buffer', stream)
    return io.TextIOWrapper(binary_stream, encoding=encoding, errors=errors) 

def hwc_mixed_001_02(self, table='', column=''):
        """Lookup the values available for querying."""
        lookup_table = self.lookup_table
        if lookup_table is not None:
            if table:
                if column:
                    column = column.upper()
                    return lookup_table[table][column]
                return lookup_table[table]
            # Show what methods are available.
            return self.lookup_methods
        return None 

def agc_mixed_001_03(self):
        """ Returns a LaTeX representation of an attribute-value matrix """
        rows = []
        headers = sorted(self.attributes.keys())

        # Header row
        header_row = r"\begin{tabular}{l" + "c" * len(headers) + "}" + "\n"
        header_row += "Attribute & " + " & ".join(headers) + r" \\ \hline"
        rows.append(header_row)

        # Data rows
        for entity, values in self.matrix.items():
            row_vals = [str(values.get(attr, "")) for attr in headers]
            rows.append(f"{entity} & {' & '.join(row_vals)} \\\\")

        rows.append(r"\end{tabular}")
        return "\n".join(rows) 

def hwc_mixed_001_04(self, exept=None):
        """
        Collects the list of dirty tabs
        """
        widgets = []
        filenames = []
        for i in range(self.count()):
            widget = self.widget(i)
            try:
                if widget.dirty and widget != exept:
                    widgets.append(widget)
                    filenames.append(widget.file.path)
            except AttributeError:
                pass
        return widgets, filenames 

def hwc_mixed_001_05(cycles, **kwargs):
    """Convenience functions for creating dq-dv data from given capacity and
    voltage cycles.

    Returns a DataFrame with a 'voltage' and a 'incremental_capacity'
    column.

        Args:
            cycles (pandas.DataFrame): the cycle data ('cycle', 'voltage',
                 'capacity', 'direction' (1 or -1)).

        Returns:
            pandas.DataFrame with columns 'cycle', 'voltage', 'dq'.

        Example:
            >>> cycles_df = my_data.get_cap(
            >>> ...   categorical_column=True,
            >>> ...   method = "forth-and-forth",
            >>> ...   label_cycle_number=True,
            >>> ... )
            >>> ica_df = ica.dqdv_cycles(cycles_df)

    """

    # TODO: should add option for normalising based on first cycle capacity
    # this is e.g. done by first finding the first cycle capacity (nom_cap)
    # (or use nominal capacity given as input) and then propagating this to
    # Converter using the key-word arguments
    #   normalize=True, normalization_factor=1.0, normalization_roof=nom_cap

    ica_dfs = list()
    cycle_group = cycles.groupby("cycle")
    for cycle_number, cycle in cycle_group:

        v, dq = dqdv_cycle(cycle, splitter=True, **kwargs)
        _ica_df = pd.DataFrame(
            {
                "voltage": v,
                "dq": dq,
            }
        )
        _ica_df["cycle"] = cycle_number
        _ica_df = _ica_df[['cycle', 'voltage', 'dq']]
        ica_dfs.append(_ica_df)

    ica_df = pd.concat(ica_dfs)
    return ica_df 

def agc_mixed_001_06(self, request_object):
        """Process the Delete Resource Request"""

        # Delete the object by its identifier
        resource_id = request_object.get('resource_id')
        if not resource_id:
            return {"status": "error", "message": "Missing resource_id"}, 400

        try:
            success = self.delete_resource(resource_id)
            if success:
                return {"status": "success", "message": f"Resource {resource_id} deleted"}, 200
            else:
                return {"status": "error", "message": "Resource not found"}, 404
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500
