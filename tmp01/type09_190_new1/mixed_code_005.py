def hwc_mixed_005_01(self, doc_id):
        """
        given a document ID, returns a merged document graph containng all
        available annotation layers.
        """
        layer_graphs = []
        for layer_name in self.layers:
            layer_files, read_function = self.layers[layer_name]
            for layer_file in layer_files:
                if fnmatch.fnmatch(layer_file, '*{}.*'.format(doc_id)):
                    layer_graphs.append(read_function(layer_file))

        if not layer_graphs:
            raise TypeError("There are no files with that document ID.")
        else:
            doc_graph = layer_graphs[0]
            for layer_graph in layer_graphs[1:]:
                doc_graph.merge_graphs(layer_graph)
        return doc_graph 

def hwc_mixed_005_02(self, listnodes):
        """
        Format ListNodes and their fields into tuples that can be printed with _print_fields().
        """
        fields = list()
        for name, node in listnodes:
            fields.append(('--', '', '', '--'))
            fields.append(('', '**%s(ListNode)**' % name, '', ''))
            for link in node.get_links():
                linked_model = link['mdl'](super_context)
                null = self._marker_true if link['null'] is True else self._marker_false
                fields.append((self._nodelist_field_prefix, link['field'],
                               '%s()' % linked_model.title, null))
            fields.extend(self._get_model_fields(node, self._nodelist_field_prefix))
        return fields 

def agc_mixed_005_03(shape, inds=None, return_directions=True):
    """
    Get list of grid edges
    :param shape:
    :param inds:
    :param return_directions:
    :return:
    """
    if inds is None:
        inds = np.arange(np.prod(shape)).reshape(shape)
    edges = []
    directions = []
    for i in range(shape[0]):
        for j in range(shape[1]):
            if i < shape[0] - 1:
                edges.append([inds[i, j], inds[i + 1, j]])
                directions.append([0, 1])
            if j < shape[1] - 1:
                edges.append([inds[i, j], inds[i, j + 1]])
                directions.append([1, 0])
    if return_directions:
        return edges, directions
    else:
        return edges 

def hwc_mixed_005_04(key):
    """Indices of the advanced indexes subspaces for mixed indexing and vindex.
    """
    if not isinstance(key, tuple):
        key = (key,)
    advanced_index_positions = [i for i, k in enumerate(key)
                                if not isinstance(k, slice)]

    if (not advanced_index_positions or
            not _is_contiguous(advanced_index_positions)):
        # Nothing to reorder: dimensions on the indexing result are already
        # ordered like vindex. See NumPy's rule for "Combining advanced and
        # basic indexing":
        # https://docs.scipy.org/doc/numpy/reference/arrays.indexing.html#combining-advanced-and-basic-indexing
        return (), ()

    non_slices = [k for k in key if not isinstance(k, slice)]
    ndim = len(np.broadcast(*non_slices).shape)
    mixed_positions = advanced_index_positions[0] + np.arange(ndim)
    vindex_positions = np.arange(ndim)
    return mixed_positions, vindex_positions 

def agc_mixed_005_05(self, bbox):
    """See base class for details."""
    # Validate the coordinates
    if not isinstance(bbox, np.ndarray):
        raise TypeError("bbox must be a numpy array")
    if bbox.shape!= (4,):
        raise ValueError("bbox must be a 1D array of length 4")
    if not np.issubdtype(bbox.dtype, np.floating):
        raise ValueError("bbox must be a floating-point array")
    if not np.all(np.isfinite(bbox)):
        raise ValueError("bbox must contain only finite values")
    if not np.all(bbox >= 0):
        raise ValueError("bbox must contain only non-negative values")
    if not np.all(bbox <= 1):
        raise ValueError("bbox must contain values in the range [0, 1]")
    encoded_example = np.zeros(self.encoded_example_size, dtype=np.float32)
    encoded_example[0] = bbox[0] * self.encoded_example_size
    encoded_example[1] = bbox[1] * self.encoded_example_size
    encoded_example[2] = np.log(bbox[2] / bbox[0]) * self.encoded_example_size
    encoded_example[3] = np.log(bbox[3] / bbox[1]) * self.encoded_example_size

    return encoded_example 

def agc_mixed_005_06(self, ostream, treeish=None, prefix=None, **kwargs):
        """Archive the tree at the given revision.

        :param ostream: file compatible stream object to which the archive will be written as bytes
        :param treeish: is the treeish name/id, defaults to active branch
        :param prefix: is the optional prefix to prepend to each filename in the archive
        :param kwargs: Additional arguments passed to git-archive

            * Use the 'format' argument to define the kind of format. Use
              specialized ostreams to write any format supported by python.
            * You may specify the special **path** keyword, which may either be a repository-relative
              path to a directory or file to place into the archive, or a list or tuple of multiple paths.

        :raise GitCommandError: in case something went wrong
        :return: self"""
        if treeish is None:
            treeish = self.active_branch
        cmd = ['git', 'archive']
        if prefix is not None:
            cmd.extend(['--prefix', prefix])
        cmd.extend([treeish, '--output', ostream.name])
        if 'format' in kwargs:
            cmd.extend(['--format', kwargs['format']])
        if 'path' in kwargs:
            if isinstance(kwargs['path'], (list, tuple)):
                cmd.extend(kwargs['path'])
            else:
                cmd.append(kwargs['path'])
        self.git.execute(cmd)
        return self
