def hwc_mixed_001_01(sam):
    """
    Parses a SAM alignment and returns a SamFile object.

    Parameters
    ----------
    sam : str or list
        Either a tab delimited SAM string, or an already tokenized 
        list of SAM fields.

    Returns
    -------
    SamRead
        a SamRead object representation of the SAM alignment.
    """

    if isinstance(sam, str):
        sam = sam.strip().split('\t')

    if not isinstance(sam, list):
        return None

    qname = sam[0]
    flag = int(sam[1])
    rname = sam[2]
    pos = int(sam[3])
    mapq = int(sam[4])
    cigar = sam[5]
    rnext = sam[6]
    pnext = int(sam[7])
    tlen = int(sam[8])
    seq = sam[9]
    qual = sam[10]

    tags = sam[11:]

    read = SamRead(qname, flag, rname, pos, mapq, cigar, rnext, pnext, tlen, seq, qual, tags)

    return read 

def agc_mixed_001_02(self, filename):
        """
        Read template from tar format with metadata.

        :type filename: str
        :param filename: Filename to read template from.

        .. rubric:: Example

        >>> template_a = Template(
        ...     name='a', st=read(), lowcut=2.0, highcut=8.0, samp_rate=100,
        ...     filt_order=4, process_length=3600, prepick=0.5)
        >>> template_a.write(
        ...     'test_template_read') # doctest: +NORMALIZE_WHITESPACE
        Template a:
         3 channels;
         lowcut: 2.0 Hz;
         highcut: 8.0 Hz;
         sampling rate 100 Hz;
         filter order: 4;
         process length: 3600 s
        >>> template_b = Template().read('test_template_read.tgz')
        >>> template_a == template_b
        True
        """
        import tarfile
        import io
        import pickle

        with tarfile.open(filename, "r:gz") as tar:
            member = tar.getmember("template.pkl")
            f = tar.extractfile(member)
            data = pickle.load(f)
            for key, value in data.items():
                setattr(self, key, value)
        return self 

def hwc_mixed_001_03(self,eigthresh=1.0e-5):
        """ Get the number of singular components with a singular
        value ratio greater than or equal to eigthresh

        Parameters
        ----------
        eigthresh : float
            the ratio of the largest to smallest singular value

        Returns
        -------
        int : int
            number of singular components

        """
        #sthresh =np.abs((self.s.x / self.s.x[0]) - eigthresh)
        sthresh = self.s.x.flatten()/self.s.x[0]
        ising = 0
        for i,st in enumerate(sthresh):
            if st > eigthresh:
                ising += 1
                #return max(1,i)
            else:
                break
        #return max(1,np.argmin(sthresh))
        return max(1,ising) 

def agc_mixed_001_04(self, name, new_data, condition, update_only=False,
                      debug=False):
        """
        Find the first row in self.df with index == name
        and condition == True.
        Update that record with new_data, then delete any
        additional records where index == name and condition == True.
        Change is inplace
        """
        # add numeric index column temporarily
        first_idx = self.df[mask].index[0]
        if not update_only:
            for col, val in new_data.items():
                if col in self.df.columns:
                    self.df.at[first_idx, col] = val

        remaining_mask = mask & (self.df.index != first_idx)
        self.df = self.df[~remaining_mask]
        if debug:
            print(f"Updated record {name}") 

def hwc_mixed_001_05(self):
        """Return a json dictionary representing this model."""
        _dict = {}
        if hasattr(self,
                   'counterexamples') and self.counterexamples is not None:
            _dict['counterexamples'] = [
                x._to_dict() for x in self.counterexamples
            ]
        if hasattr(self, 'pagination') and self.pagination is not None:
            _dict['pagination'] = self.pagination._to_dict()
        return _dict 

def agc_mixed_001_06(arg_plot):
    """Build set of needed field variables.

    Each var is a tuple, first component is a scalar field, second component is
    either:

    - a scalar field, isocontours are added to the plot.
    - a vector field (e.g. 'v' for the (v1,v2,v3) vector), arrows are added to
      the plot.

    Args:
        arg_plot (str): string with variable names separated with
            ``,`` (figures), and ``+`` (same plot).
    Returns:
        set of str: set of needed field variables.
    """
    vars_set = set()
    for plot_group in arg_plot.split(','):
        for var_pair in plot_group.split('+'):
            if '=' in var_pair:
                scalar, other = var_pair.split('=')
                vars_set.add(scalar.strip())
                vars_set.add(other.strip())
            else:
                vars_set.add(var_pair.strip())
    return vars_set
