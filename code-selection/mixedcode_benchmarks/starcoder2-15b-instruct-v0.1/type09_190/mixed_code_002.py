def hwc_mixed_002_01(prompt):
    """Ask user for agreeing to data set licenses."""
    # raw_input returns the empty string for "enter"
    yes = set(['yes', 'y'])
    no = set(['no','n'])

    try:
        print(prompt)
        choice = input().lower()
        # would like to test for exception here, but not sure if we can do that without importing IPython
    except:
        print('Stdin is not implemented.')
        print('You need to set')
        print('overide_manual_authorize=True')
        print('to proceed with the download. Please set that variable and continue.')
        raise


    if choice in yes:
        return True
    elif choice in no:
        return False
    else:
        print(("Your response was a " + choice))
        print("Please respond with 'yes', 'y' or 'no', 'n'") 

def hwc_mixed_002_02(self):
    """Returns a list of entities for this blob."""
    start = 0
    end = 0
    prev_tag = u'O'
    chunks = []
    for i, (w, tag) in enumerate(self.ne_chunker.annotate(self.words)):
      if tag != prev_tag:
        if prev_tag == u'O':
          start = i
        else:
          chunks.append(Chunk(self.words[start: i], start, i, tag=prev_tag,
                              parent=self))
        prev_tag = tag
    if tag != u'O':
      chunks.append(Chunk(self.words[start: i+1], start, i+1, tag=tag,
                          parent=self))
    return chunks 

def agc_mixed_002_03(self, block_id, addresses):
        """Returns a list of address/data pairs (str, bytes)"""
        if not isinstance(block_id, str):
            raise TypeError("block_id must be a str")
        if not isinstance(addresses, list):
            raise TypeError("addresses must be a list")
        if not all(isinstance(address, str) for address in addresses):
            raise TypeError("addresses must be a list of str")
        if not all(len(address) == 42 for address in addresses):
            raise ValueError("addresses must be a list of 42-char str")
        results = []
        for address in addresses:
            data = self.state_db.get(block_id, address)
            results.append((address, data))

        return results 

def agc_mixed_002_04(start, end, periods, offset):
    """Generate a regular range of cftime.datetime objects with a
    given time offset.

    Adapted from pandas.tseries.offsets.generate_range.

    Parameters
    ----------
    start : cftime.datetime, or None
        Start of range
    end : cftime.datetime, or None
        End of range
    periods : int, or None
        Number of elements in the sequence
    offset : BaseCFTimeOffset
        An offset class designed for working with cftime.datetime objects

    Returns
    -------
    A generator object
    """
    if periods is not None:
        if start is not None:
            end = start + offset * (periods - 1)
        else:
            start = end - offset * (periods - 1)
    else:
        if start is not None and end is not None:
            periods = int((end - start) / offset) + 1
        else:
            raise ValueError("Either `periods` or both `start` and `end` must be specified")

    if start is not None:
        yield start

    for _ in range(periods - 1):
        start += offset
        yield start 

def hwc_mixed_002_05(self):
        """Delete an existing profile."""
        self.validate_profile_exists()

        profile_data = self.profiles.get(self.args.profile_name)
        fqfn = profile_data.get('fqfn')
        with open(fqfn, 'r+') as fh:
            data = json.load(fh)
            for profile in data:
                if profile.get('profile_name') == self.args.profile_name:
                    data.remove(profile)
            fh.seek(0)
            fh.write(json.dumps(data, indent=2, sort_keys=True))
            fh.truncate()

        if not data:
            # remove empty file
            os.remove(fqfn) 

def agc_mixed_002_06(self, instance_count, node_reg, node_ids):
        # Select primaries for current view_no
        if instance_count == 0:
            return []

        """
        Build a set of names of primaries, it is needed to avoid
        duplicates of primary nodes for different replicas.
        """
        primaries = set()
        for node_id in node_ids:
            node = node_reg.get(node_id)
            if node is None:
                continue
            if node.is_primary:
                primaries.add(node.name)
        return list(primaries)
