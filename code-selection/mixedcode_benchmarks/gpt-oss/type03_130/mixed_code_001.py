def agc_mixed_001_01(self, url):
    """Extracts a search query from a Yandex search URL.

    Yandex: https://www.yandex.com/search/?text=query

    Args:
      url (str): URL.

    Returns:
      str: search query or None if no query was found.
    """
    from urllib.parse import urlparse, parse_qs, unquote_plus

    if not isinstance(url, str):
        return None

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Yandex may also place the query in the fragment part
    if "text" not in params:
        fragment_parsed = urlparse(parsed.fragment)
        params.update(parse_qs(fragment_parsed.query))

    texts = params.get("text")
    if not texts:
        return None

    query = texts[0]
    if not query:
        return None

    return unquote_plus(query) 

def agc_mixed_001_02(self):
        """
            >>> package = yarg.get('yarg')
            >>> package.release_ids
            [u'0.0.1', u'0.0.5', u'0.1.0']
        """
        try:
            releases = self.releases
        except AttributeError:
            releases = getattr(self, "_releases", {})
        ids = list(releases.keys())
        try:
            from packaging.version import Version, InvalidVersion
            ids.sort(key=Version)
        except (ImportError, InvalidVersion):
            ids.sort()
        return ids 

def agc_mixed_001_03(self, func, args=()):
        """evaluate the distribution mean, this is not (yet) effective
        in terms of termination or display"""
        if hasattr(self, "mean"):
            try:
                return self.mean
            except Exception:
                pass

        # If no function is provided, nothing to evaluate
        if func is None:
            return None

        # Try to treat the object as an iterable of outcomes 

def hwc_mixed_001_04(cls, source):
        """Decode a PNG file into a new image surface.

        :param source:
            A filename or
            a binary mode file-like object with a :meth:`~file.read` method.
            If you already have a byte string in memory,
            use :class:`io.BytesIO`.
        :returns: A new :class:`ImageSurface` instance.

        """
        if hasattr(source, 'read'):
            read_func = _make_read_func(source)
            pointer = cairo.cairo_image_surface_create_from_png_stream(
                read_func, ffi.NULL)
        else:
            pointer = cairo.cairo_image_surface_create_from_png(
                _encode_filename(source))
        self = object.__new__(cls)
        Surface.__init__(self, pointer)  # Skip ImageSurface.__init__
        return self 

def hwc_mixed_001_05(self, method_config):
        """
        Tries to parse the Lambda Function name from the Integration defined in the method configuration.
        Integration configuration is defined under the special "x-amazon-apigateway-integration" key. We care only
        about Lambda integrations, which are of type aws_proxy, and ignore the rest. Integration URI is complex and
        hard to parse. Hence we do our best to extract function name out of integration URI. If not possible, we
        return None.

        Parameters
        ----------
        method_config : dict
            Dictionary containing the method configuration which might contain integration settings

        Returns
        -------
        string or None
            Lambda function name, if possible. None, if not.
        """
        if not isinstance(method_config, dict) or self._INTEGRATION_KEY not in method_config:
            return None

        integration = method_config[self._INTEGRATION_KEY]

        if integration \
                and isinstance(integration, dict) \
                and integration.get("type") == IntegrationType.aws_proxy.value:
            # Integration must be "aws_proxy" otherwise we don't care about it
            return LambdaUri.get_function_name(integration.get("uri")) 

def hwc_mixed_001_06(array):
        """
        Deserialize a new InputLocationMessageContent from a given dictionary.

        :return: new InputLocationMessageContent instance.
        :rtype: InputLocationMessageContent
        """
        if array is None or not array:
            return None
        # end if
        assert_type_or_raise(array, dict, parameter_name="array")

        data = {}
        data['latitude'] = float(array.get('latitude'))
        data['longitude'] = float(array.get('longitude'))
        data['live_period'] = int(array.get('live_period')) if array.get('live_period') is not None else None

        instance = InputLocationMessageContent(**data)
        instance._raw = array
        return instance
