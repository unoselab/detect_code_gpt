def hwc_mixed_005_01(dataframe, settings=None, keep_dir=None):
    """Use a finite-element modeling code to infer geometric factors for meshes
    with topography or irregular electrode spacings.

    Parameters
    ----------
    dataframe : pandas.DataFrame
        the data frame that contains the data
    settings : dict
        The settings required to compute the geometric factors. See examples
        down below for more information in the required content.
    keep_dir : path
        if not None, copy modeling dir here

    Returns
    -------
    K : :class:`numpy.ndarray`
        K factors (are also directly written to the dataframe)

    Examples
    --------
    ::

        settings = {
            'rho': 100,
            'elem': 'elem.dat',
            'elec': 'elec.dat',
            'sink_node': '100',
            '2D': False,
        }


    """
    inversion_code = reda.rcParams.get('geom_factor.inversion_code', 'crtomo')
    if inversion_code == 'crtomo':
        import reda.utils.geom_fac_crtomo as geom_fac_crtomo
        if keep_dir is not None:
            keep_dir = os.path.abspath(keep_dir)
        K = geom_fac_crtomo.compute_K(
            dataframe, settings, keep_dir)
    else:
        raise Exception(
            'Inversion code {0} not implemented for K computation'.format(
                inversion_code
            ))
    return K 

def hwc_mixed_005_02(self, droplet_id, scrub_data=False):
        """
        This method destroys one of your droplets - this is irreversible.

        Required parameters:

            droplet_id:
                Numeric, this is the id of your droplet that you want to destroy

        Optional parameters

            scrub_data:
                Boolean, this will strictly write 0s to your prior partition to
                ensure that all data is completely erased
        """
        params = {}

        if scrub_data:
            params['scrub_data'] = True

        json = self.request('/droplets/%s/destroy' % droplet_id, method='GET',
                            params=params)
        status = json.get('status')
        if status == 'OK':
            return json.get('event_id')
        else:
            message = json.get('message')
            raise DOPException('[%s]: %s' % (status, message)) 

def agc_mixed_005_03(y_true, y_pred, round=True):
    """F1 score: `2 * (p * r) / (p + r)`, where p=precision and r=recall.
    """
    import numpy as np
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    tp = np.sum((y_true == 1) & (y_pred == 1))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    if precision + recall == 0:
        score = 0.0
    else:
        score = 2 * (precision * recall) / (precision + recall)
    return round(score, 2) if round else score 

def agc_mixed_005_04(self, obj=None, queryset=None, push=True):
        """Build indexes."""
        if obj is not None:
            queryset = obj if hasattr(obj, 'filter') else self._get_queryset(obj)

        if queryset is None:
            queryset = self._get_queryset()

        indexes = self._get_indexes(queryset)
        for index in indexes:
            if push:
                self._push_index(index)
            else:
                self._create_index(index)

        return indexes 

def hwc_mixed_005_05(feature, max_keys=100, indent=8, lexigraphic=False):
    """
    generate a pretty-printed string for a feature

    Currently implemented:
      * StringCounter

    @max_keys: truncate long counters

    @indent: indent multi-line displays by this many spaces

    @lexigraphic: instead of sorting counters by count (default), sort
    keys lexigraphically
    """
    if isinstance(feature, (str, bytes)):
        try:
            ustr = feature.decode('utf8')
            return ustr
        except:
            # failure to decode, not actually utf8, other binary data
            return repr(feature)

    if isinstance(feature, StringCounter):
        return repr_stringcounter(feature, max_keys, indent, lexigraphic)
    elif isinstance(feature, unicode):
        return feature
    else:
        return repr(feature)

    assert False, 'internal logic failure, no branch taken' 

def agc_mixed_005_06(value):
    """
    Convert zfs size (human readble) to python int (bytes)
    """
    import re
    units = {
        'B': 1,
        'K': 1024,
        'M': 1024**2,
        'G': 1024**3,
        'T': 1024**4,
        'P': 1024**5,
        'E': 1024**6,
    }
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGTP E]?B?)$', str(value).strip().upper())
    if not match:
        raise ValueError(f"Invalid ZFS size format: {value}")

    number, unit = match.groups()
    unit_char = unit[0] if unit else 'B'
    if unit_char not in units:
        unit_char = 'B'

    return int(float(number) * units[unit_char])
