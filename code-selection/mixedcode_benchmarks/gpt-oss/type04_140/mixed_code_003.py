def agc_mixed_003_01(results, split_id='results', output_stream=None):
    """
    Log `results` readably to `output_stream`, with a header
    containing `split_id`.

    :param results: a dictionary of summary statistics from an evaluation
    :type results: dict(str -> object)

    :param str split_id: an identifier for the source of `results` (e.g. 'dev')

    :param file output_stream: the file-like object to which to log the results
        (default: stdout)
    :type split_id: str
    """
    import sys
    if output_stream is None:
        output_stream = sys.stdout
    header = f"--- {split_id} results ---"
    print(header, file=output_stream)
    if not isinstance(results, dict):
        print(f"Invalid results type: {type(results)}", file=output_stream)
        return
    for key in sorted(results):
        try:
            value = results[key]
        except Exception as e:
            value = f"<error: {e}>"
        print(f"{key}: {value}", file=output_stream)
    print("-" * len(header), file=output_stream) 

def agc_mixed_003_02(obj, role, scopes, delete):
    """Add or delete role-to-permission lookup entry."""
    if delete:
        if role in obj:
            current = obj[role]
            for scope in scopes:
                current.discard(scope)
            if not current:
                del obj[role]
    else:
        current = obj.setdefault(role, set())
        for scope in scopes:
            current.add(scope)
    return obj 

def hwc_mixed_003_03(self, callback, context):  # pragma: no cover
        """Apply the HTTPError wrapper to the callback.
        """

        def wrapper(*args, **kwargs):
            try:
                return callback(*args, **kwargs)
            except bottle.HTTPError as error:
                return self.error_wrapper.from_status(
                    status_line=error.status_line,
                    msg=error.body
                )

        return wrapper 

def hwc_mixed_003_04(self, t):
        """
        Parse a list of samples to make sure that it has the correct
        dimensions.

        :param t: ``(nsamples,)`` or ``(nsamples, ndim)``
            The list of samples. If 1-D, this is assumed to be a list of
            one-dimensional samples otherwise, the size of the second
            dimension is assumed to be the dimension of the input space.

        Raises:
            ValueError: If the input dimension doesn't match the dimension of
                the kernel.

        """
        t = np.atleast_1d(t)
        # Deal with one-dimensional data.
        if len(t.shape) == 1:
            t = np.atleast_2d(t).T

        # Double check the dimensions against the kernel.
        if len(t.shape) != 2 or (self.kernel is not None and
                                 t.shape[1] != self.kernel.ndim):
            raise ValueError("Dimension mismatch")

        return t 

def agc_mixed_003_05(self, conf_evt):
        """Implements neighbor configuration change listener.
        """
        try:
            enabled = conf_evt["enabled"]
        except (TypeError, KeyError):
            enabled = getattr(conf_evt, "enabled", None)
        if enabled is None:
            return
        if getattr(self, "enabled", None) != enabled:
            self.enabled = enabled
            if hasattr(self, "_enabled_changed"):
                self._enabled_changed()
        return 

def hwc_mixed_003_06(self, object):
        """
        Sets the object of this ServicePackageQuotaHistoryResponse.
        Always set to 'service-package-quota-history'.

        :param object: The object of this ServicePackageQuotaHistoryResponse.
        :type: str
        """
        if object is None:
            raise ValueError("Invalid value for `object`, must not be `None`")
        allowed_values = ["service-package-quota-history"]
        if object not in allowed_values:
            raise ValueError(
                "Invalid value for `object` ({0}), must be one of {1}"
                .format(object, allowed_values)
            )

        self._object = object
