def hwc_mixed_005_01(self, value, redis):
        """
        Validates data obtained from a request in ISO 8061 and returns it in Datetime data type
        """

        value = self.value_or_default(value)

        self.validate_required(value)

        if value is None:
            return None

        if type(value) == str:
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                raise InvalidFieldError(self.name)

        return value 

def agc_mixed_005_02(obj, filename, filetype='auto', ndarray_to_list=False, squeeze=True):
    """Writes annotation in file.

    :param filetype:
        auto
        yaml
        pkl, pickle
        pklz, picklezip
    :param ndarray_to_list: convert ndarrays in obj to lists
    :param squeeze: squeeze ndarray

    """
    # import json
    # with open(filename, mode='w') as f:
    #    json.dump(annotation,f)
    if filetype == 'auto':
        filetype = 'yaml'

    if filetype == 'yaml':
        with open(filename, 'w') as f:
            yaml.dump(obj, f, default_flow_style=False)
    elif filetype == 'pkl':
        with open(filename, 'wb') as f:
            pickle.dump(obj, f)
    elif filetype == 'pklz':
        with gzip.open(filename, 'wb') as f:
            pickle.dump(obj, f)
    else:
        raise ValueError('filetype not supported') 

def hwc_mixed_005_03(self, init_kwargs=None, additional_parents_aliases=None):
        """Returns a list of CategoryList objects, associated with
        this model instance.

        :param dict|None init_kwargs:
        :param list|None additional_parents_aliases:
        :rtype: list|CategoryRequestHandler
        :return:
        """

        if self._category_editor is not None:  # Return editor lists instead of plain lists if it's enabled.
            return self._category_editor.get_lists()

        from .toolbox import get_category_lists
        init_kwargs = init_kwargs or {}

        catlist_kwargs = {}
        if self._category_lists_init_kwargs is not None:
            catlist_kwargs.update(self._category_lists_init_kwargs)
        catlist_kwargs.update(init_kwargs)

        lists = get_category_lists(catlist_kwargs, additional_parents_aliases, obj=self)

        return lists 

def agc_mixed_005_04(self, callback, data):
        """Execute the callback in another thread. Wait for and return the results."""
        if callback is None:
            return None

        if not isinstance(callback, Callback):
            raise TypeError("callback must be a Callback")

        if not isinstance(data, dict):
            raise TypeError("data must be a dict")

        if self.thread_pool is None:
            self.thread_pool = ThreadPool(self.thread_pool_size)

        future = self.thread_pool.submit(callback.execute, data)
        return future.result() 

def hwc_mixed_005_05(s='', newline=True, stream=STDOUT):
    """Prints given string to stdout."""
    max_width_ctx = _get_max_width_context()
    if max_width_ctx:
        cols, separator = max_width_ctx[-1]
        s = max_width(s, cols, separator)

    if newline:
        s = tsplit(s, NEWLINES)
        s = map(str, s)
        indent = ''.join(INDENT_STRINGS)

        s = (str('\n' + indent)).join(s)

    _str = ''.join((
        ''.join(INDENT_STRINGS),
        str(s),
        '\n' if newline else ''
    ))
    stream(_str) 

def agc_mixed_005_06(hypervisor, identifier, storage_pool, configuration, image, logger):
    """Disk image cloning.

    Given an original disk image it clones it into a new one, the clone will be created within the storage pool.

    The following values are set into the disk XML configuration:

      * name
      * target/path
      * target/permission/label
      * backingStore/path if copy on write is enabled

    """
    logger.info("Cloning disk image %s", identifier)

    # Get the original disk image
    original_disk = hypervisor.get_disk(identifier)

    # Create the new disk image
    new_disk = hypervisor.create_disk(storage_pool, configuration)

    # Clone the disk image
    hypervisor.clone_disk(original_disk, new_disk)

    # Set the disk image name
    new_disk.set_name(image.name)

    # Set the disk image path
    new_disk.set_path(image.path)

    # Set the disk image label
    new_disk.set_label(image.label)

    # Set the disk image backing store path
    if image.cow:
        new_disk.set_backing_store_path(image.backing_store_path)

    # Return the new disk image
    return new_disk
