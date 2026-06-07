def agc_mixed_004_01(self, **kwargs):
        """Auto Generated Code
        """
        config = ET.Element("config")
        port_profile = ET.SubElement(config, "port-profile", xmlns="urn:brocade.com:mgmt:brocade-port-profile")
        if kwargs.pop('delete_port_profile', False) is True:
            delete_port_profile = config.find('.//port-profile')
            delete_port_profile.set('operation', 'delete')

        port_profile_name_key = ET.SubElement(port_profile, "port-profile-name")
        port_profile_name_key.text = kwargs.pop('port_profile_name')
        port_profile_qos_profile_cee = ET.SubElement(port_profile, "port-profile-qos-profile-cee")
        port_profile_qos_profile_cee.text = kwargs.pop('port_profile_qos_profile_cee')

        callback = kwargs.pop('callback', self._callback)
        return callback(config) 

def hwc_mixed_004_02(map_type):
    """
    Load all maps of a given type into a dictionary.

    Color maps are loaded as BrewerMap objects. Dictionary is
    keyed by map name and then integer numbers of defined
    colors. There is an additional 'max' key that points to the
    color map with the largest number of defined colors.

    Parameters
    ----------
    map_type : {'Sequential', 'Diverging', 'Qualitative'}

    Returns
    -------
    maps : dict of BrewerMap

    """
    seq_maps = COLOR_MAPS[map_type]

    loaded_maps = {}

    for map_name in seq_maps:
        loaded_maps[map_name] = {}

        for num in seq_maps[map_name]:
            inum = int(num)
            colors = seq_maps[map_name][num]['Colors']

            bmap = BrewerMap(map_name, map_type, colors)

            loaded_maps[map_name][inum] = bmap

        max_num = int(max(seq_maps[map_name].keys(), key=int))
        loaded_maps[map_name]['max'] = loaded_maps[map_name][max_num]

    return loaded_maps 

def hwc_mixed_004_03(self, key):
        """ Delete file key from database
        """
        with self.get_conn() as conn:
            try:
                c = conn.cursor()
                c.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
            except:
                getLogger().exception("Cannot delete")
                return None 

def agc_mixed_004_04(self, instance, mode='view', default=None, field=None):
        """
        This function returns the visibility of the widget depending on whether
        the rejection workflow is enabled or not.
        """
        if not self.rejection_workflow:
            return True
        if mode == 'view':
            return True
        if mode == 'edit':
            return False
        if mode == 'create':
            return False
        if mode == 'list':
            return False
        return default 

def agc_mixed_004_05(self, name=None):
        """Forwards messages logged on background to Robot Framework log.

        By default forwards all messages logged by all threads, but can be
        limited to a certain thread by passing thread's name as an argument.

        Logged messages are removed from the message storage.
        """
        if name is None:
            for thread_name in self._messages.keys():
                self.log_background_messages(thread_name)
        else:
            if name not in self._messages:
                return
            for message in self._messages[name]:
                self.log_message(message)
            del self._messages[name] 

def hwc_mixed_004_06(n, C):
    """
    Return a Wishart random matrix.

    :Parameters:
      n : int
        Degrees of freedom, > 0.
      C : matrix
        Symmetric and positive definite
    """
    # return rwishart(n, np.linalg.inv(C))

    p = np.shape(C)[0]
    # Need cholesky decomposition of precision matrix C^-1?
    sig = np.linalg.cholesky(C)

    if n <= (p-1):
        raise ValueError('Wishart parameter n must be greater '
                         'than size of matrix.')

    norms = np.random.normal(size=(p * (p - 1)) // 2)
    chi_sqs = np.sqrt(np.random.chisquare(df=np.arange(n, n - p, -1)))
    A = flib.expand_triangular(chi_sqs, norms)

    flib.dtrmm_wrap(sig, A, side='L', uplo='L', transa='N', alpha=1.)
    w = np.asmatrix(np.dot(A, A.T))
    flib.symmetrize(w)
    return w
