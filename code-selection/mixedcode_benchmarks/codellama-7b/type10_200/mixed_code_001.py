def agc_mixed_001_01(self):
        """
        Return a Listing object as Dictionary
        :return: dict
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'currency': self.currency,
            'quantity': self.quantity,
            'category': self.category,
            'tags': self.tags,
            'images': self.images,
            'attributes': self.attributes,
            'variants': self.variants,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'deleted_at': self.deleted_at,
        } 

def hwc_mixed_001_02(self, configuration):
    """Starts profiling.

    Args:
      configuration (ProfilingConfiguration): profiling configuration.
    """
    if not configuration:
      return

    if configuration.HaveProfileMemoryGuppy():
      self._guppy_memory_profiler = profilers.GuppyMemoryProfiler(
          self._name, configuration)
      self._guppy_memory_profiler.Start()

    if configuration.HaveProfileMemory():
      self._memory_profiler = profilers.MemoryProfiler(
          self._name, configuration)
      self._memory_profiler.Start()

    if configuration.HaveProfileProcessing():
      identifier = '{0:s}-processing'.format(self._name)
      self._processing_profiler = profilers.ProcessingProfiler(
          identifier, configuration)
      self._processing_profiler.Start()

    if configuration.HaveProfileSerializers():
      identifier = '{0:s}-serializers'.format(self._name)
      self._serializers_profiler = profilers.SerializersProfiler(
          identifier, configuration)
      self._serializers_profiler.Start()

    if configuration.HaveProfileStorage():
      self._storage_profiler = profilers.StorageProfiler(
          self._name, configuration)
      self._storage_profiler.Start()

    if configuration.HaveProfileTasks():
      self._tasks_profiler = profilers.TasksProfiler(self._name, configuration)
      self._tasks_profiler.Start() 

def hwc_mixed_001_03(self, options):
        """
        Perform translation of feed options passed in as keyword
        arguments to CouchDB/Cloudant equivalent.
        """
        translation = dict()
        for key, val in iteritems_(options):
            self._validate(key, val, feed_arg_types(self._source))
            try:
                if isinstance(val, STRTYPE):
                    translation[key] = val
                elif not isinstance(val, NONETYPE):
                    arg_converter = TYPE_CONVERTERS.get(type(val), json.dumps)
                    translation[key] = arg_converter(val)
            except Exception as ex:
                raise CloudantArgumentError(115, key, ex)
        return translation 

def agc_mixed_001_04(self, spec_or_id=None, multi=True, **kwargs):
        """Remove a document(s) from this collection.

        **DEPRECATED** - Use :meth:`delete_one` or :meth:`delete_many` instead.

        .. versionchanged:: 3.0
           Removed the `safe` parameter. Pass ``w=0`` for unacknowledged write
           operations.
        """
        warnings.warn(
            "Collection.remove is deprecated. Use delete_one or delete_many instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if spec_or_id is None:
            if multi:
                return self.delete_many(**kwargs)
            else:
                return self.delete_one(**kwargs)
        else:
            if isinstance(spec_or_id, dict):
                return self.delete_many(spec_or_id, **kwargs)
            else:
                return self.delete_one(spec_or_id, **kwargs) 

def hwc_mixed_001_05(vm_name, call=None):
    """
    Call GCE 'stop' on the instance.

    .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop myinstance
    """
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    conn = get_conn()

    __utils__['cloud.fire_event'](
        'event',
        'stop instance',
        'salt/cloud/{0}/stopping'.format(vm_name),
        args={'name': vm_name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    result = conn.ex_stop_node(
        conn.ex_get_node(vm_name)
    )

    __utils__['cloud.fire_event'](
        'event',
        'stop instance',
        'salt/cloud/{0}/stopped'.format(vm_name),
        args={'name': vm_name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return result 

def agc_mixed_001_06(self, entity_id, sp_config):
        """ Instantiate user-specified processor or default to an all-access base processor.
            Raises an exception if the configured processor class can not be found or initialized.
        """
        processor_class = sp_config.get('processor_class', None)
        if processor_class is None:
            return BaseProcessor(entity_id, sp_config)
        else:
            try:
                processor_class = import_string(processor_class)
            except ImportError:
                raise Exception('Unable to import processor class: %s' % processor_class)
            try:
                processor = processor_class(entity_id, sp_config)
            except TypeError:
                raise Exception('Unable to instantiate processor class: %s' % processor_class)
            return processor
