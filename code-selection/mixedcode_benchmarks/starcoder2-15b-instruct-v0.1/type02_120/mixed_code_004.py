def hwc_mixed_004_01(tree_column, model_column_index, format_str,
                      cell_renderer=None):
    """
    Set the text of a cell according to a [format][1] string.

    [1]: https://docs.python.org/2/library/string.html#formatstrings

    Args:

        tree_column (gtk.TreeViewColumn) : Tree view to append columns to.
        model_column_index (int) : Index in list store model corresponding to
            tree view column.
        format_str (str) : Format string as accepted by Python string `format`
            method (e.g., `'{value}'`).  N.B., the value of a cell is passed to
            the `format` method as a keyword argument.
        cell_renderer (gtk.CellRenderer) : Cell renderer for column.  If
            `None`, defaults to all cell renderers for column.

    Returns:

        None
    """
    def set_property(column, cell_renderer, list_store, iter, store_i):
        value = list_store[iter][store_i]
        cell_renderer.set_property('text', format_str.format(value=value))
    if cell_renderer is None:
        cells = tree_column.get_cells()
    else:
        cells = [cell_renderer]
    for cell_renderer_i in cells:
        tree_column.set_cell_data_func(cell_renderer_i, set_property,
                                       model_column_index) 

def agc_mixed_004_02(self, size=None):
        """Returns the next set of rows of a query result, returning a
        list of tuples. When no more rows are available, it returns an
        empty list.

        The number of rows returned can be specified using the size argument,
        which defaults to one

        :param size: ``int`` number of rows to return
        :returns: ``list`` of fetched rows
        """
        if size is None:
            size = 1
        rows = []
        for _ in range(size):
            try:
                rows.append(next(self.result_iterator))
            except StopIteration:
                break
        return rows 

def agc_mixed_004_03(self):
        """
        Groups and then sorts the nodes according to the criteria passed into
        the Plot constructor.
        """
        groups = {}
        for node in self.nodes:
            group_key = node.group_key
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(node)

        for group in groups.values():
            group.sort(key=lambda node: node.sort_key)

        return groups 

def hwc_mixed_004_04(packages, options=None, fatal=False):
    """Install one or more packages."""
    if options is None:
        options = ['--option=Dpkg::Options::=--force-confold']

    cmd = ['apt-get', '--assume-yes']
    cmd.extend(options)
    cmd.append('install')
    if isinstance(packages, six.string_types):
        cmd.append(packages)
    else:
        cmd.extend(packages)
    log("Installing {} with options: {}".format(packages,
                                                options))
    _run_apt_command(cmd, fatal) 

def hwc_mixed_004_05(self, content):
    """Whether to issue another GET bucket call.

    Args:
      content: response XML.

    Returns:
      True if should, also update self._options for the next request.
      False otherwise.
    """
    if ('max-keys' in self._options and
        self._options['max-keys'] <= common._MAX_GET_BUCKET_RESULT):
      return False

    elements = self._find_elements(
        content, set([common._T_IS_TRUNCATED,
                      common._T_NEXT_MARKER]))
    if elements.get(common._T_IS_TRUNCATED, 'false').lower() != 'true':
      return False

    next_marker = elements.get(common._T_NEXT_MARKER)
    if next_marker is None:
      self._options.pop('marker', None)
      return False
    self._options['marker'] = next_marker
    return True 

def agc_mixed_004_06(config_path_or_dict=None):
    """
    Read config from given path string or dict object.

    :param config_path_or_dict:
    :type config_path_or_dict: str or dict
    :return: Returns config object or None if not found.
    :rtype: :class:`revision.config.Config`
    """
    if config_path_or_dict is None:
        return None
    elif isinstance(config_path_or_dict, str):
        if os.path.isfile(config_path_or_dict):
            with open(config_path_or_dict) as f:
                config_dict = f.read()
        else:
            return None
    elif isinstance(config_path_or_dict, dict):
        config_dict = config_path_or_dict
    else:
        return None
    return Config(config_dict)
