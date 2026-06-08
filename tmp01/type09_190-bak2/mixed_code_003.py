def hwc_mixed_003_01(dset1,dset2):
    """calculates maximal voxel-wise difference in datasets (in %)

    Useful for checking if datasets have the same data. For example, if the maximum difference is
    < 1.0%, they're probably the same dataset"""
    for dset in [dset1,dset2]:
        if not os.path.exists(dset):
            nl.notify('Error: Could not find file: %s' % dset,level=nl.level.error)
            return float('inf')
    try:
        dset1_d = nib.load(dset1)
        dset2_d = nib.load(dset2)
        dset1_data = dset1_d.get_data()
        dset2_data = dset2_d.get_data()
    except IOError:
        nl.notify('Error: Could not read files %s and %s' % (dset1,dset2),level=nl.level.error)
        return float('inf')
    try:
        old_err = np.seterr(divide='ignore',invalid='ignore')
        max_val = 100*np.max(np.ma.masked_invalid(np.double(dset1_data - dset2_data) / ((dset1_data+dset2_data)/2)))
        np.seterr(**old_err)
        return max_val
    except ValueError:
        return float('inf') 

def hwc_mixed_003_02(self):
        """
        Returns combined size in bytes for all repository files
        """

        size = 0
        try:
            tip = self.get_changeset()
            for topnode, dirs, files in tip.walk('/'):
                for f in files:
                    size += tip.get_file_size(f.path)
                for dir in dirs:
                    for f in files:
                        size += tip.get_file_size(f.path)

        except RepositoryError:
            pass
        return size 

def agc_mixed_003_03(self, *args, **kwargs):
        """
        Returns
        -------
        S : np.array
            Returns the pareto set for a problem. Points in the X space to be known to be optimal!
        """
        S = []
        for i in range(len(self.X)):
            is_pareto = True
            for j in range(len(self.X)):
                if all(self.X[j][k] >= self.X[i][k] for k in range(len(self.X[0]))):
                    if all(self.X[j][k] > self.X[i][k] for k in range(len(self.X[0]))):
                        is_pareto = False
                        break
            if is_pareto:
                S.append(self.X[i])
        return np.array(S) 

def agc_mixed_003_04(self):
        """
        Return the unicode XML snippet for the ``<c:val>`` element describing
        this series, containing the series values and their spreadsheet range
        reference.
        """
        values = self._values
        if values is None:
            values = self._values = self._series_values()
        value_xml = []
        for value in values:
            value_xml.append(
                '<c:ptCount val="{count}"/><c:numCache>{values}</c:numCache>'
               .format(
                    count=len(value),
                    values="".join(value)
                )
            )
        return "".join(value_xml) 

def hwc_mixed_003_05(self, grammars):
        """Process provided grammars by parsing them into Python objects."""
        for path in self.default_grammars:
            grammars.insert(0, open(os.path.relpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                 os.path.normcase(path)))))
        for fo in grammars:
            logging.debug("Processing grammar content of %s", fo.name)
            self.set_namespace(os.path.splitext(os.path.basename(fo.name))[0])
            for line in fo:
                self.parse_line(line)
            self.handle_empty_line()
        self.resolve_xref()
        self.calculate_leaf_paths() 

def agc_mixed_003_06(self, device):
        """ Updates the device information based on files from its 'mount_point'
            @param device Dictionary containing device information
        """
        device_name = device['name']
        device_mount_point = device['mount_point']
        device_files = os.listdir(device_mount_point)
        for file_name in device_files:
            file_path = os.path.join(device_mount_point, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_modification_time = os.path.getmtime(file_path)
                device[file_name] = {
                   'size': file_size,
                   'modification_time': file_modification_time
                }
