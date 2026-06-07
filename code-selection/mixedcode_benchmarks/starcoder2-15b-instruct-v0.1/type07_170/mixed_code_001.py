def agc_mixed_001_01(self, attribute_list, named_attributes=None, force_primary_key=None):
        """
        derive a new heading by selecting, renaming, or computing attributes.
        In relational algebra these operators are known as project, rename, and extend.
        :param attribute_list:  the full list of existing attributes to include
        :param force_primary_key:  attributes to force to be converted to primary
        :param named_attributes:  dictionary of renamed attributes
        """
        if named_attributes is None:
            named_attributes = {}
        if force_primary_key is None:
            force_primary_key = []
        new_heading = []
        for attribute in attribute_list:
            if attribute in named_attributes:
                new_heading.append(named_attributes[attribute])
            else:
                new_heading.append(attribute)
        if len(force_primary_key) > 0:
            new_heading = force_primary_key + new_heading
        return new_heading 

def agc_mixed_001_02(self, tup_tree, acceptable):
        """
        Parse a list/tuple of elements from child nodes.

        The children can be any of the listed acceptable types, but they
        must all be the same.
        """

        result = []
        for child in tup_tree:
            if isinstance(child, acceptable):
                result.append(child)
            elif isinstance(child, tuple):
                result.extend(self.list_of_same(child, acceptable))
            else:
                raise TypeError("Invalid child type: {}".format(type(child)))

        if len(set(result)) == 1:
            return result
        else:
            raise ValueError("All children must be the same type.") 

def hwc_mixed_001_03(self, key):
        """
        Returns a list with keys of this DAWG that are prefixes of the ``key``.
        """
        res = []
        index = self.dct.ROOT
        if not isinstance(key, bytes):
            key = key.encode('utf8')

        pos = 1

        for ch in key:
            index = self.dct.follow_char(int_from_byte(ch), index)
            if not index:
                break

            if self._has_value(index):
                res.append(key[:pos].decode('utf8'))
            pos += 1

        return res 

def hwc_mixed_001_04(instance, *args, **kwargs):
    """
    Used to process the lines of the endpoint list.
    """
    with open(instance.upload.file.name, mode='rb') as f:
        lines = f.readlines()
    for url in lines:
        if len(url) > 255:
            LOGGER.debug('Skipping this endpoint, as it is more than 255 characters: %s' % url)
        else:
            if Endpoint.objects.filter(url=url, catalog=instance.catalog).count() == 0:
                endpoint = Endpoint(url=url, endpoint_list=instance)
                endpoint.catalog = instance.catalog
                endpoint.save()
    if not settings.REGISTRY_SKIP_CELERY:
        update_endpoints.delay(instance.id)
    else:
        update_endpoints(instance.id) 

def hwc_mixed_001_05():
    """
    Taken from ``django.contrib.admin.autodiscover`` and used to run
    any calls to the ``processor_for`` decorator.
    """
    global LOADED
    if LOADED:
        return
    LOADED = True
    for app in get_app_name_list():
        try:
            module = import_module(app)
        except ImportError:
            pass
        else:
            try:
                import_module("%s.page_processors" % app)
            except:
                if module_has_submodule(module, "page_processors"):
                    raise 

def agc_mixed_001_06(self, tdata1, tdata2, seeds):
        """
        it works with seed labels:
        0: nothing
        1: object 1 - full seeds
        2: object 2 - full seeds
        3: object 1 - not a training seeds
        4: object 2 - not a training seeds
        """
        self.hard_hard_constraints = np.zeros((len(tdata1), len(tdata2)), dtype=np.int32)
        for i, seed in enumerate(seeds):
            if seed == 1:
                self.hard_hard_constraints[i, :] = 1
            elif seed == 2:
                self.hard_hard_constraints[:, i] = 1
            elif seed == 3:
                self.hard_hard_constraints[i, :] = 2
            elif seed == 4:
                self.hard_hard_constraints[:, i] = 2
