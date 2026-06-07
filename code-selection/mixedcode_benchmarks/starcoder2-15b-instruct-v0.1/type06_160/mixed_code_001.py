def agc_mixed_001_01(self, wst, type):
        """
        Resolves the slots and reference samples in accordance with the
        Worksheet Template passed in and the type passed in.
        Returns a list of dictionaries
        :param wst: Worksheet Template that defines the layout
        :param type: type of analyses ('b' for blanks, 'c' for controls)
        :return: list of dictionaries
        """
        reference_samples = []
        for row in wst:
            for col in row:
                if col['type'] == type:
                    reference_samples.append({
                       'slot': col['slot'],
                       'reference_sample': col['reference_sample']
                    })
        return reference_samples 

def hwc_mixed_001_02(self, facet_name, field, ranges=[]):
        """
        Range facet allow to specify a set of ranges and get both the number of docs (count) that fall within each range, and aggregated data either based on the field, or using another field.
        http://www.elasticsearch.org/guide/reference/api/search/facets/range-facet.html

        > ElasticFacet().range('range1', 'field_name', [ slice(50), slice(20,70), slice(50,-1) ])
        {
          "range1" : {
            "range" : {
                "field" : "field_name",
                "ranges" : [
                    { "to" : 50 },
                    { "from" : 20, "to" : 70 },
                    { "from" : 70, "to" : 120 },
                    { "from" : 150 }
                ]
            }
           }
        }
        """

        self[facet_name] = {'range': {'field': field, 'ranges': []}}
        for s in ranges:
            if not isinstance(s, slice):
                continue
            entry = dict()
            if s.start:
                entry['from'] = s.start
            if s.stop != -1:
                entry['to'] = s.stop
            self[facet_name]['range']['ranges'].append(entry)

        return self 

def agc_mixed_001_03(seeds, zoom):
    """
    Smart zoom for sparse matrix. If there is resize to bigger resolution
    thin line of label could be lost. This function prefers labels larger
    then zero. If there is only one small voxel in larger volume with zeros
    it is selected.
    """
    # import scipy
    # loseeds=seeds
    seeds_new = np.zeros(seeds.shape, dtype=np.int16)
    for i in range(seeds.shape[0]):
        for j in range(seeds.shape[1]):
            for k in range(seeds.shape[2]):
                if seeds[i, j, k] > 0:
                    seeds_new[i*zoom:(i+1)*zoom, j*zoom:(j+1)*zoom, k*zoom:(k+1)*zoom] = 1
                else:
                    if np.sum(seeds[i*zoom:(i+1)*zoom, j*zoom:(j+1)*zoom, k*zoom:(k+1)*zoom]) == 1:
                        seeds_new[i*zoom:(i+1)*zoom, j*zoom:(j+1)*zoom, k*zoom:(k+1)*zoom] = 1
    return seeds_new 

def agc_mixed_001_04(self, src_dir):
        """
        Load defaults from configuration file:
         - from the source/directory/.dirsync file (prioritary)
         - and/or a %HOME%/.dirsync user config file
        """

        # last files override previous ones
        cfg_file = os.path.join(src_dir, '.dirsync')
        if os.path.isfile(cfg_file):
            with open(cfg_file) as f:
                self.cfg = json.load(f)
        else:
            cfg_file = os.path.expanduser('~/.dirsync')
            if os.path.isfile(cfg_file):
                with open(cfg_file) as f:
                    self.cfg = json.load(f)
            else:
                self.cfg = {} 

def hwc_mixed_001_05():
        """Wraps errors.  Call it in `except` clause::

           try:
               do_something()
           except:
               self.erred()

        """
        exc_type, exc, tb = sys.exc_info()
        if issubclass(exc_type, socket.timeout):
            raise TimedOut
        elif issubclass(exc_type, requests.ConnectionError):
            internal_exc = exc.args[0]
            if isinstance(internal_exc, ReadTimeoutError):
                raise TimedOut
            else:
                raise ConnectionError(exc)
        elif issubclass(exc_type, requests.RequestException):
            raise EtcException(exc)
        reraise(exc_type, exc, tb) 

def hwc_mixed_001_06(self, *args, **kwargs) -> None:
        """
        Called at each iteration.

        This function does time measurements, updates timing in the monitoring context and calls
        all monitoring tasks.
        """

        # Update timing and the iteration number in the monitoring context.
        current_timestamp = get_hr_time()
        self._context.optimisation_time += current_timestamp - self._last_timestamp
        self._context.total_time = current_timestamp - self._start_timestamp
        self._context.optimiser_updated = False
        if not self._context.optimisation_finished:
            self._context.iteration_no += 1

        # Call all monitoring functions
        for func in self._monitor_tasks:
            func(self._context, *args, **kwargs)

        # Remember the time when the control is returned back to the optimiser, so that the next
        # optimisation step can be accurately timed.
        self._last_timestamp = get_hr_time()
