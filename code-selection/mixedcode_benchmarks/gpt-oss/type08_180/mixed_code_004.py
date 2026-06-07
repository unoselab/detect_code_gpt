def hwc_mixed_004_01(self, message):
        """ The callback subscribed to the broker """
        payload = message['payload']
        if message['$'] == 'before':
            self._commands.append({'level': self._depth,
                                   'payload': payload,
                                   'logs': []})
            self._depth += 1
        else:
            while not self._queue.empty():
                self._commands[-1]['logs'].append(self._queue.get())
            self._depth = max(self._depth-1, 0) 

def agc_mixed_004_02(self, tm, angular_integration=False, verbose=False):
        """Initialize the scattering lookup tables.

        Initialize the scattering lookup tables for the different geometries.
        Before calling this, the following attributes must be set:
           num_points, m_func, axis_ratio_func, D_max, geometries
        and additionally, all the desired attributes of the Scatterer class
        (e.g. wavelength, aspect ratio).

        Args:
            tm: a Scatterer instance.
            angular_integration: If True, also calculate the 
                angle-integrated quantities (scattering cross section, 
                extinction cross section, asymmetry parameter). These are 
                needed to call the corresponding functions in the scatter 
                module when PSD integration is active. The default is False.
            verbose: if True, print information about the progress of the 
                calculation (which may take a while). If False (default), 
                run silently.
        """
        import numpy as np

        # Verify required attributes
        required_attrs = ["num_points", "m_func", "axis_ratio_func", "D_max", "geometries"]
        for attr in required_attrs:
            if not hasattr(self, attr):
                raise AttributeError(f"Attribute '{attr}' must be set before initializing scatter tables.")

        # Prepare size array (avoid zero to prevent singularities)
        sizes = np.linspace(0, self.D_max, self.num_points, dtype=float)
        if sizes[0] == 0:
            sizes[0] = np.nextafter(0, 1)  # smallest positive float

        # Containers for lookup tables
        self._scatter_tables = {}
        self._angular 

def hwc_mixed_004_03(self, width, cap_style_line=CAP_STYLE.flat, cap_style_point=CAP_STYLE.round):
        """Turns line or point into a buffered polygon."""
        shape = self._shape
        if isinstance(shape, (LineString, MultiLineString)):
            return self.__class__(
                shape.buffer(width / 2, cap_style=cap_style_line),
                self.crs
            )
        elif isinstance(shape, (Point, MultiPoint)):
            return self.__class__(
                shape.buffer(width / 2, cap_style=cap_style_point),
                self.crs
            )
        else:
            return self 

def agc_mixed_004_04(self, item_id, action, tag):
        """ wrapper around actual HTTP POST string for modify tags """
        if action not in ("add", "remove"):
            raise ValueError(f"Invalid action '{action}'. Expected 'add' or 'remove'.")
        payload = {"item_id": item_id, "action": action, "tag": tag}
        url = f"{self.base_url.rstrip('/')}/modify_item_tag"
        # Prefer a custom _post method if the class provides one
        post_func = getattr(self, "_post", None)
        if callable(post_func):
            response = post_func(url, json=payload)
        else:
            # Fallback to a requests.Session if available, else plain requests
            if hasattr(self, "session") and hasattr(self.session, "post"):
                response 

def agc_mixed_004_05(samples, name='bootstrap', ndim=2):
    """
    Ensures that `samples` is an `ndim` numpy array. Raises a helpful
    ValueError if otherwise.
    """
    import numpy as np

    # Convert to ndarray if possible
    if not isinstance(samples, np.ndarray):
        try:
            samples = np.asarray(samples)
        except Exception as exc:
            raise ValueError(
                f"`{name}` must be a numpy.ndarray or convertible to one; conversion failed: {exc}"
            ) from exc

    # Verify dimensionality
    if samples.ndim != ndim:
        raise ValueError(
            f"`{name}` must be a {ndim}-dimensional array, but got shape {samples.shape} "
            f"(ndim={samples.ndim})."
        )

    return samples 

def hwc_mixed_004_06(self, b):
        """
        Perform a wrapped LTE comparison only considering the SI bounds

        :param a: The first operand
        :param b: The second operand
        :return: True if a <= b, False otherwise
        """

        a = self
        if a.is_empty:
            return True

        if a.is_top and b.is_top:
            return True

        elif a.is_top:
            return False

        elif b.is_top:
            return True

        if b._surrounds_member(a.lower_bound) and b._surrounds_member(a.upper_bound):
            if ((b.lower_bound == a.lower_bound and b.upper_bound == a.upper_bound)
                or not a._surrounds_member(b.lower_bound) or not a._surrounds_member(b.upper_bound)):
                return True
        return False
