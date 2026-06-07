def hwc_mixed_005_01(self, mtf_graph):
    """Initializer for self._mtf_dimension_name_to_size_gcd.

    Args:
      mtf_graph: an mtf.Graph.

    Returns:
      A {string: int}, mapping the name of an MTF dimension to the greatest
      common divisor of all the sizes it has. All these sizes being evenly
      divisible by some x is equivalent to the GCD being divisible by x.
    """
    mtf_dimension_name_to_size_gcd = {}
    for mtf_operation in mtf_graph.operations:
      for mtf_tensor in mtf_operation.outputs:
        for mtf_dimension in mtf_tensor.shape.dims:
          mtf_dimension_name_to_size_gcd[mtf_dimension.name] = fractions.gcd(
              mtf_dimension_name_to_size_gcd.get(mtf_dimension.name,
                                                 mtf_dimension.size),
              mtf_dimension.size)

    return mtf_dimension_name_to_size_gcd 

def hwc_mixed_005_02(persistent_object, target_rest_class=None, attribute_filter=None):
    """
    Adapts a single persistent instance to a REST model; at present this is a
    common method for all persistent backends.

    Refer to: https://groups.google.com/forum/#!topic/prestans-discuss/dO1yx8f60as
    for discussion on this feature
    """

    # try and get the adapter and the REST class for the persistent object
    if target_rest_class is None:
        adapter_instance = registry.get_adapter_for_persistent_model(persistent_object)
    else:
        if inspect.isclass(target_rest_class):
            target_rest_class = target_rest_class()

        adapter_instance = registry.get_adapter_for_persistent_model(persistent_object, target_rest_class)

    # would raise an exception if the attribute_filter differs from the target_rest_class
    if attribute_filter is not None and isinstance(attribute_filter, parser.AttributeFilter):
        parser.AttributeFilter.from_model(target_rest_class).conforms_to_template_filter(attribute_filter)

    # convert filter to immutable if it isn't already
    if isinstance(attribute_filter, parser.AttributeFilter):
        attribute_filter = attribute_filter.as_immutable()

    return adapter_instance.adapt_persistent_to_rest(persistent_object, attribute_filter) 

def agc_mixed_005_03(items, targets, **kwargs):
    """First-Fit Decreasing

    This is perhaps the simplest packing heuristic;
    it simply packs items in the next available bin.

    This algorithm differs only from Next-Fit Decreasing
    in having a 'sort'; that is, the items are pre-sorted
    (largest to smallest).

    Complexity O(n^2)
    """
    items.sort(reverse=True)
    bins = []
    for item in items:
        for bin in bins:
            if bin.can_fit(item):
                bin.add(item)
                break
        else:
            bin = Bin()
            bin.add(item)
            bins.append(bin)
    return bins 

def agc_mixed_005_04(self, env, target_name='control',
                     file_name='control.json',
                     encoder_cls=SConsEncoder):
        """
        Adds a target to build a control file at each of the current leaves.

        :param env: SCons Environment object
        :param target_name: Name for target in nest
        :param file_name: Name for output file.
        """
        def build_control(target, source, env):
            control = {}
            for key, value in env.items():
                if not key.startswith('_'):
                    control[key] = value
            with open(str(target[0]), 'w') as f:
                json.dump(control, f, cls=encoder_cls)
        env.Command(target_name, file_name, build_control) 

def agc_mixed_005_05(self, fp_, header):
        """Read data block"""
        if not fp_.readable():
            raise ValueError("File object must be readable")
        if not isinstance(header, dict):
            raise ValueError("header must be a dict")
        data = []
        for line in fp_:
            line = line.strip()
            if line:
                data.append(line)
        return data 

def hwc_mixed_005_06(self, name, make_copy=True):
        """Return step from steps library.

        Optionally, the step returned is a deep copy from the step in the steps
        library, so additional information (e.g., about whether the step was
        scattered) can be stored in the copy.

        Args:
            name (str): name of the step in the steps library.
            make_copy (bool): whether a deep copy of the step should be
                returned or not (default: True).

        Returns:
            Step from steps library.

        Raises:
            ValueError: The requested step cannot be found in the steps
                library.
        """
        self._closed()

        s = self.steps_library.get_step(name)
        if s is None:
            msg = '"{}" not found in steps library. Please check your ' \
                  'spelling or load additional steps'
            raise ValueError(msg.format(name))
        if make_copy:
            s = copy.deepcopy(s)
        return s
