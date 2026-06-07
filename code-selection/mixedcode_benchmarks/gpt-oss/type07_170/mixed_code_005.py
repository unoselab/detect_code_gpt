def agc_mixed_005_01(self, filename, mtime, size):
        """Store real file mtime in meta data.

        This is needed on FTP targets, because FTP servers don't allow to set
        file mtime, but use to the upload time instead.
        We also record size and upload time, so we can detect if the file was
        changed by other means and we have to discard our meta data.
        """
        import time
        now = time.time()
        meta = getattr(self, "_meta", None)
        if meta is None:
            self._meta = {}
            meta = self._meta
        meta[filename] = {"mtime": mtime, "size": size, "upload_time": now}
        saver = getattr(self, "_save_meta", None)
        if callable(saver):
            try:
                saver()
            except Exception:
                pass 

def agc_mixed_005_02(
            self, limit_to=100, max_calls=None, parameters=None,
            since_when=None, start_record=0, verbose=False):
        """
        Retrieve all memberships updated since "since_when"

        Loop over queries of size limit_to until either a non-full queryset
        is returned, or max_depth is reached (used in tests). Then the
        recursion collapses to return a single concatenated list.
        """
        results = []
        calls_made = 0
        offset = start_record

        while True:
            if max_calls is not None and calls_made >= max_calls:
                break

            # Build request parameters for this batch
            batch_params = {} if parameters is None else dict(parameters)
            batch_params.update({"limit": limit_to, "offset": offset})
            if since_when is not None:
                batch_params["updated_since"] = since 

def agc_mixed_005_03(self, diff_key=None, diff_list='intersect'):
        """Deletes an attribute from all of the intersect objects"""
        if diff_key is None:
            raise ValueError("diff_key must be provided")
        target = getattr(self, diff_list, None)
        if target is None:
            raise AttributeError(f"{self.__class__.__name__!s} has no attribute {diff_list!r}")
        for obj in target:
            if isinstance(obj, dict):
                obj.pop(diff_key, None)
            else:
                if hasattr(obj, diff_key):
                    delattr(obj, diff_key) 

def hwc_mixed_005_04(self):
        """
        cDNA coding sequence (from start codon to stop codon, without
        any introns)
        """
        if self.sequence is None:
            return None

        start = self.first_start_codon_spliced_offset
        end = self.last_stop_codon_spliced_offset

        # If start codon is the at nucleotide offsets [3,4,5] and
        # stop codon is at nucleotide offsets  [20,21,22]
        # then start = 3 and end = 22.
        #
        # Adding 1 to end since Python uses non-inclusive ends in slices/ranges.

        # pylint: disable=invalid-slice-index
        # TODO(tavi) Figure out pylint is not happy with this slice
        return self.sequence[start:end + 1] 

def hwc_mixed_005_05(self, d):
        """
        Ensures all values are encoded in UTF-8 and converts them to lowercase

        """
        for k, v in d.items():
            if isinstance(v, str):
                d[k] = v.encode('utf8').lower()
            if isinstance(v, list):
                for index,item in enumerate(v):
                    item = item.encode('utf8').lower()
                    v[index] = item
            if isinstance(v, dict):
                d[k] = self._utf8_encode(v)

        return d 

def hwc_mixed_005_06(*iterables):
    """roundrobin('ABC', 'D', 'EF') --> A D E B F C"""
    raise NotImplementedError('not sure if this implementation is correct')
    # http://stackoverflow.com/questions/11125212/interleaving-lists-in-python
    #sentinel = object()
    #return (x for x in chain(*zip_longest(fillvalue=sentinel, *iterables)) if x is not sentinel)
    pending = len(iterables)
    if six.PY2:
        nexts = cycle(iter(it).next for it in iterables)
    else:
        nexts = cycle(iter(it).__next__ for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = cycle(islice(nexts, pending))
