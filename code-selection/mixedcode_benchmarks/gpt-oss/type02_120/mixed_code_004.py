def hwc_mixed_004_01(self):
        """Get success url"""
        messages.success(self.request, "Successfully deleted ({})".format(self.object))
        if self.success_url:
            return reverse(self.success_url)

        if 'app' in self.kwargs and 'model' in self.kwargs:
            return reverse('trionyx:model-list', kwargs={
                'app': self.kwargs.get('app'),
                'model': self.kwargs.get('model'),
            })

        return '/' 

def agc_mixed_004_02(a, b):
    """
    Recursively merge dicts.

    recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.

    @see http://www.xormedia.com/recursively-merge-dictionaries-in-python/
    """
    result = a.copy()
    for key, value in b.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = dict_merge(result[key], value)
        else:
            result[key] = value
    return result 

def hwc_mixed_004_03(self, **kwargs):
        """Return the BFD minimum receive interval XML.

        You should not use this method.
        You probably want `BGP.bfd`.

        Args:
            min_rx (str): BFD receive interval in milliseconds (300, 500, etc)
            delete (bool): Remove the configuration if ``True``.

        Returns:
            XML to be passed to the switch.

        Raises:
            None
        """
        method_name = 'rbridge_id_router_router_bgp_router_bgp_attributes_' \
                      'bfd_interval_min_rx'
        bfd_rx = getattr(self._rbridge, method_name)
        config = bfd_rx(**kwargs)
        if kwargs['delete']:
            tag = 'min-rx'
            config.find('.//*%s' % tag).set('operation', 'delete')
            pass
        return config 

def hwc_mixed_004_04(self):
        """locate manifests and return filepaths thereof"""
        manifest_dir = mp_util.dot_mavproxy()

        ret = []
        for file in os.listdir(manifest_dir):
            try:
                file.index("manifest")
                ret.append(os.path.join(manifest_dir,file))
            except ValueError:
                pass
        return ret 

def agc_mixed_004_05(self, suppress):
        """Enables or disables pagination header by setting `sysparm_suppress_pagination_header`

        :param suppress: bool
        """
        if not isinstance(suppress, bool):
            raise TypeError("suppress must be a bool")
        # Ensure the instance has a dictionary to hold query parameters
        if not hasattr(self, "_params") or not isinstance(self._params, dict):
            self._params = {}
        # ServiceNow expects the value as a lowercase string
        self._params["sysparm_suppress_pagination_header"] = "true" if suppress else "false"
        return self 

def agc_mixed_004_06(req, model):
    """ Return an array of Filter objects. """

    filters = []
    # Assume `req` behaves like Flask's request with `args` dict of query parameters
    # and `model` has attributes corresponding to filterable fields.
    for key, value in getattr(req, "args", {}).items():
        if hasattr(model, key):
            # Create a Filter object for each matching query parameter.
            # The Filter class is expected to be defined/imported elsewhere.
            filters.append(Filter(key, value))
    return filters
