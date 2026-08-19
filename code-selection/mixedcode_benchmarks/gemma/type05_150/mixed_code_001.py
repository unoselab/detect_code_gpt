def agc_mixed_001_01(self, f_values, idx1):  # will most likely be removed
        """obsolete and subject to removal (TODO),
        return indices for negative ("active") update of the covariance matrix
        assuming that ``f_values[idx1[i]]`` and ``f_values[-1-i]`` are
        the corresponding mirrored values

        computes the index of the worse solution sorted by the f-value of the
        better solution.

        TODO: when the actual mirror was rejected, it is better
        to return idx1 instead of idx2.

        Remark: this function might not be necessary at all: if the worst solution
        is the best mirrored, the covariance matrix updates cancel (cave: weights
        and learning rates), which seems what is desirable. If the mirror is bad,
        as strong negative update is made, again what is desirable.
        And the fitness--step-length correlation is in part addressed by
        using flat weights.

        """
        idx2 = []
        for i in range(len(idx1)):
            # The mirrored value is at -1-i
            # We want the index of the worse solution (higher f-value)
            # sorted by the f-value of the better solution.
            if f_values[idx1[i]] < f_values[-1-i]:
                idx2.append(-1-i)
            else:
                idx2.append(idx1[i])
        return idx2 

def agc_mixed_001_02(self, fname=None, root=None, shuffle=False):
        """
        save imglist to disk

        Parameters:
        ----------
        fname : str
            saved filename
        """
        import pickle
        import os

        if fname is None:
            fname = 'imglist.pkl'

        save_path = fname
        if root is not None:
            save_path = os.path.join(root, fname)

        data = self.imglist
        if shuffle:
            import random
            random.shuffle(data)

        with open(save_path, 'wb') as f:
            pickle.dump(data, f) 

def hwc_mixed_001_03(cls, napp_list):
        """Format the NApp list to be printed."""
        mgr = NAppsManager()
        enabled = mgr.get_enabled()
        installed = mgr.get_installed()
        napps = []
        for napp, desc in sorted(napp_list):
            status = 'i' if napp in installed else '-'
            status += 'e' if napp in enabled else '-'
            status = '[{}]'.format(status)
            name = '{}/{}'.format(*napp)
            napps.append((status, name, desc))
        cls.print_napps(napps) 

def agc_mixed_001_04(self, arg):
        """ Takes an argument and updates the hash.
        The argument can be an np.array, string, or list
        of things that are convertable to strings.
        """
        import numpy as np
        import hashlib

        if isinstance(arg, np.ndarray):
            data = arg.tobytes()
        elif isinstance(arg, str):
            data = arg.encode('utf-8')
        elif isinstance(arg, list):
            data = "".join(map(str, arg)).encode('utf-8')
        else:
            data = str(arg).encode('utf-8')

        if not hasattr(self, '_hash_obj'):
            self._hash_obj = hashlib.sha256()
        self._hash_obj.update(data) 

def hwc_mixed_001_05(self):
        """
        Return a copy of the distribution.

        Returns
        -------
        GaussianDistribution: copy of the distribution

        Examples
        --------
        >>> import numpy as np
        >>> from pgmpy.factors.distributions import GaussianDistribution as GD
        >>> gauss_dis = GD(variables=['x1', 'x2', 'x3'],
        ...                mean=[1, -3, 4],
        ...                cov=[[4, 2, -2],
        ...                     [2, 5, -5],
        ...                     [-2, -5, 8]])
        >>> copy_dis = gauss_dis.copy()
        >>> copy_dis.variables
        ['x1', 'x2', 'x3']
        >>> copy_dis.mean
        array([[ 1],
                [-3],
                [ 4]])
        >>> copy_dis.covariance
        array([[ 4,  2, -2],
                [ 2,  5, -5],
                [-2, -5,  8]])
        >>> copy_dis.precision_matrix
        array([[ 0.3125    , -0.125     ,  0.        ],
                [-0.125     ,  0.58333333,  0.33333333],
                [ 0.        ,  0.33333333,  0.33333333]])
        """
        copy_distribution = GaussianDistribution(variables=self.variables,
                                                 mean=self.mean.copy(),
                                                 cov=self.covariance.copy())
        if self._precision_matrix is not None:
            copy_distribution._precision_matrix = self._precision_matrix.copy()

        return copy_distribution 

def hwc_mixed_001_06(self, lon, lat):
        """
        Projects geodesic coordinates to screen
        :param lon: longitude
        :param lat: latitude
        :return: x,y screen coordinates
        """
        if type(lon) == list:
            lon = np.array(lon)
        if type(lat) == list:
            lat = np.array(lat)

        lat_rad = np.radians(lat)
        n = 2.0 ** self.zoom
        xtile = (lon + 180.0) / 360.0 * n
        ytile = (1.0 - np.log(np.tan(lat_rad) + (1 / np.cos(lat_rad))) / math.pi) / 2.0 * n
        x = (xtile * TILE_SIZE).astype(int)
        y = (SCREEN_H - ytile * TILE_SIZE).astype(int)
        return x, y
