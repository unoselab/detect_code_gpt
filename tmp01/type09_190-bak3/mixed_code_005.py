def agc_mixed_005_01(self, garbage=0, clean=0, deflate=0, ascii=0, expand=0, linear=0, pretty=0, decrypt=1):
        """Write document to a bytes object."""

        if garbage:
            return b'GARBAGE'
        if clean:
            return b'CLEAN'
        if deflate:
            return b'DEFLATE'
        if ascii:
            return b'ASCII'
        if expand:
            return b'EXPAND'
        if linear:
            return b'LINEAR'
        if pretty:
            return b'PRETTY'
        if decrypt:
            return b'DECRYPT'
        return b'' 

def hwc_mixed_005_02(key):
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

def agc_mixed_005_03(self):
        """
        Get past PythonKC meetup events.

        Returns
        -------
        List of ``pythonkc_meetups.types.MeetupEvent``, ordered by event time,
        descending.

        Exceptions
        ----------
        * PythonKCMeetupsBadJson
        * PythonKCMeetupsBadResponse
        * PythonKCMeetupsMeetupDown
        * PythonKCMeetupsNotJson
        * PythonKCMeetupsRateLimitExceeded

        """

        response = self.client.get_events()
        if response.status_code!= 200:
            raise PythonKCMeetupsBadResponse(response.status_code)
        try:
            json_response = response.json()
        except ValueError:
            raise PythonKCMeetupsNotJson(response.text)
        if 'errors' in json_response:
            raise PythonKCMeetupsBadJson(json_response['errors'])
        if 'rate_limit_exceeded' in json_response:
            raise PythonKCMeetupsRateLimitExceeded(json_response['rate_limit_exceeded'])
        if 'problem' in json_response:
            raise PythonKCMeetupsMeetupDown(json_response['problem'])
        events = [MeetupEvent(event) for event in json_response]
        events.sort(key=lambda event: event.time, reverse=True)

        return events 

def hwc_mixed_005_04(self, listnodes):
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

def hwc_mixed_005_05(self, doc_id):
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

def agc_mixed_005_06(self):
        """
        Returns errors on:
        Certificate, PrivateKey or Chain not being properly formatted
        Arn not existing if its provided
        PrivateKey size > 2048
        Certificate expired or is not yet in effect

        Does not return errors on:
        Checking Certificate is legit, or a selfsigned chain is provided

        :return: str(JSON) for response
        """
        errors = []
        if not self.certificate:
            errors.append("Certificate not properly formatted")
        if not self.private_key:
            errors.append("PrivateKey not properly formatted")
        if not self.chain:
            errors.append("Chain not properly formatted")
        if self.arn and not self.certificate_manager.get_certificate(self.arn):
            errors.append("Arn not existing")
        if len(self.private_key) > 2048:
            errors.append("PrivateKey size > 2048")
        if self.certificate.not_valid_before > datetime.now() or self.certificate.not_valid_after < datetime.now():
            errors.append("Certificate expired or is not yet in effect")
        return json.dumps(errors)
