def agc_mixed_001_01(self, seqprop, structprop, chain_id,
                                      seq_ident_cutoff=0.5, allow_missing_on_termini=0.2,
                                      allow_mutants=True, allow_deletions=False,
                                      allow_insertions=False, allow_unresolved=True):
        """Report if a structure's chain meets the defined cutoffs for sequence quality."""
        seq_ident = seqprop.get_sequence_identity(structprop, chain_id)
        if seq_ident < seq_ident_cutoff:
            return False
        missing_residues = seqprop.get_missing_residues(structprop, chain_id)
        if missing_residues > allow_missing_on_termini:
            return False
        if not allow_mutants and seqprop.has_mutants(structprop, chain_id):
            return False
        if not allow_deletions and seqprop.has_deletions(structprop, chain_id):
            return False
        if not allow_insertions and seqprop.has_insertions(structprop, chain_id):
            return False
        if not allow_unresolved and seqprop.has_unresolved(structprop, chain_id):
            return False
        return True 

def agc_mixed_001_02(
        self, table_data, primary_key=None, add_primary_key_column=False, index_attrs=None
    ):
        """
        Create a table from :py:class:`tabledata.TableData`.

        :param tabledata.TableData table_data: Table data to create.
        :param str primary_key: |primary_key|
        :param tuple index_attrs: |index_attrs|

        .. seealso::
            :py:meth:`.create_table_from_data_matrix`
        """

        if not isinstance(table_data, TableData):
            raise ValueError("table_data must be an instance of TableData")
        if primary_key and primary_key not in table_data.headers:
            raise ValueError(f"primary_key {primary_key} not found in table_data headers")
        if index_attrs:
            for index_attr in index_attrs:
                if index_attr not in table_data.headers:
                    raise ValueError(f"index_attr {index_attr} not found in table_data headers")
        data_matrix = table_data.to_data_matrix()
        table = self.create_table_from_data_matrix(
            data_matrix, primary_key=primary_key, add_primary_key_column=add_primary_key_column, index_attrs=index_attrs
        )

        return table 

def hwc_mixed_001_03(self, time):
        """
        Set point in time used to check validity of certificates for
        Time can be either python datetime object or number of seconds
        sinse epoch
        """
        if isinstance(time, datetime) or isinstance(time,
                                                             datetime.date):
            seconds = int(time.strftime("%s"))
        elif isinstance(time, int):
            seconds = time
        else:
            raise TypeError("datetime.date, datetime.datetime or integer " +
                            "is required as time argument")
        raise NotImplementedError 

def hwc_mixed_001_04(self):
        """Build a key from the "important" parts of a selector: elements,
        classes, ids.
        """
        parts = set()
        for node in self.simple_selectors:
            for token in node.tokens:
                if token[0] not in ':[':
                    parts.add(token)

        if not parts:
            # Should always have at least ONE key; selectors with no elements,
            # no classes, and no ids can be indexed as None to avoid a scan of
            # every selector in the entire document
            parts.add(None)

        return frozenset(parts) 

def hwc_mixed_001_05(self, urns, aff4_type=None, mode="r"):
    """Opens many urns efficiently, returning cached objects when possible."""
    not_opened_urns = []
    _ValidateAFF4Type(aff4_type)

    for urn in urns:
      key = self._ObjectKey(urn, mode)
      try:
        result = self._objects_cache[key]
        if aff4_type is not None and not isinstance(result, aff4_type):
          continue
        yield result

      except KeyError:
        not_opened_urns.append(urn)

    if not_opened_urns:
      for obj in FACTORY.MultiOpen(
          not_opened_urns, follow_symlinks=False, mode=mode, token=self._token):
        key = self._ObjectKey(obj.urn, mode)
        self._objects_cache[key] = obj

        if aff4_type is not None and not isinstance(obj, aff4_type):
          continue

        yield obj 

def agc_mixed_001_06(self, archive_paths, objects_getter, bboxes_getter,
                         prefixes=None):
    """Yields examples."""
    for archive_path in archive_paths:
        with tf.io.gfile.GFile(archive_path, "rb") as f:
            archive = zipfile.ZipFile(f)
            for name in archive.namelist():
                if prefixes and not any(name.startswith(p) for p in prefixes):
                    continue
                with archive.open(name) as file:
                    obj = objects_getter(file)
                    bboxes = bboxes_getter(obj)
                    yield name, obj, bboxes
