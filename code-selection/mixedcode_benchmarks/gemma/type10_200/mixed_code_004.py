def agc_mixed_004_01(cls, binary_view):
        """Creates a new object AttributeHeader from a binary stream. The binary
        stream can be represented by a byte string, bytearray or a memoryview of the
        bytearray.

        Args:
            binary_view (memoryview of bytearray) - A binary stream with the
                information of the attribute

        Returns:
            AttributeHeader: New object using hte binary stream as source
        """
        import struct
        # Assuming AttributeHeader is the class being instantiated (cls)
        # and it expects specific fields from the binary_view.
        # Since the exact structure of AttributeHeader isn't provided,
        # a standard implementation for a binary header parser follows:

        # Example: reading a 4-byte integer and a 4-byte length
        # Adjust the format string based on the actual AttributeHeader specification
        try:
            data = struct.unpack_from('<II', binary_view)
            return cls(*data)
        except (struct.error, TypeError):
            # Fallback: if the class takes the view directly or has a different init
            return cls(binary_view) 

def hwc_mixed_004_02(pid=None, portserver_address=None):
    """A pure python implementation of PickUnusedPort.

    Args:
      pid: PID to tell the portserver to associate the reservation with. If
        None, the current process's PID is used.
      portserver_address: The address (path) of a unix domain socket
        with which to connect to a portserver, a leading '@'
        character indicates an address in the "abstract namespace".  OR
        On systems without socket.AF_UNIX, this is an AF_INET address.
        If None, or no port is returned by the portserver at the provided
        address, the environment will be checked for a PORTSERVER_ADDRESS
        variable.  If that is not set, no port server will be used.

    Returns:
      A port number that is unused on both TCP and UDP.

    Raises:
      NoFreePortFoundError: No free port could be found.
    """
    try:  # Instead of `if _free_ports:` to handle the race condition.
        port = _free_ports.pop()
    except KeyError:
        pass
    else:
        _owned_ports.add(port)
        return port
    # Provide access to the portserver on an opt-in basis.
    if portserver_address:
        port = get_port_from_port_server(portserver_address, pid=pid)
        if port:
            return port
    if 'PORTSERVER_ADDRESS' in os.environ:
        port = get_port_from_port_server(os.environ['PORTSERVER_ADDRESS'],
                                         pid=pid)
        if port:
            return port
    return _pick_unused_port_without_server() 

def agc_mixed_004_03(frame, urls, directory, min_file_size, max_file_size, no_redirects):
	"""
	called when user wants serial downloading
	"""

	# create directory to save files
	import requests
	import os
	from tkinter import messagebox

	for url in urls:
	    try:
	        response = requests.get(url, stream=True, allow_redirects=not no_redirects, timeout=10)
	        if response.status_code != 200:
	            continue

	        content_length = response.headers.get('Content-Length')
	        if content_length:
	            size = int(content_length)
	            if not (min_file_size <= size <= max_file_size):
	                continue

	        filename = os.path.join(directory, url.split('/')[-1] or 'downloaded_file')
	        with open(filename, 'wb') as f:
	            for chunk in response.iter_content(chunk_size=8192):
	                f.write(chunk)
	    except Exception as e:
	        print(f"Error downloading {url}: {e}")

	messagebox.showinfo("Status", "Download process completed.") 

def hwc_mixed_004_04(self, subdomain):
        """Get faces which are fully in subdomain.
        """
        if subdomain is None:
            # https://stackoverflow.com/a/42392791/353337
            return numpy.s_[:]

        if subdomain not in self.subdomains:
            self._mark_vertices(subdomain)

        # A face is inside if all its edges are in.
        # An edge is inside if all its nodes are in.
        is_in = self.subdomains[subdomain]["vertices"][self.idx_hierarchy]
        # Take `all()` over all axes except the last two (face_ids, cell_ids).
        n = len(is_in.shape)
        is_inside = numpy.all(is_in, axis=tuple(range(n - 2)))

        if subdomain.is_boundary_only:
            # Filter for boundary
            is_inside = is_inside & self.is_boundary_facet

        return is_inside 

def hwc_mixed_004_05(self, sites, rup, dists, imt, stddev_types, 
        mag_conversion_sigma=0.0):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """
        # extract dictionaries of coefficients specific to required
        # intensity measure type
        C = self.COEFFS[imt]

        # clip distance at 4 km, minimum distance for which the equation is
        # valid (see section 2.2.4, page 201). This also avoids singularity
        # in the equation
        rhypo = dists.rhypo
        rhypo[rhypo < 4.] = 4.

        mean = C['a'] * rup.mag + C['b'] * rhypo - np.log10(rhypo)

        mean[sites.vs30 >= 800] += C['c1']
        mean[sites.vs30 < 800] += C['c2']

        # convert from log10 to ln, and from cm/s2 to g
        mean = mean * np.log(10) - 2 * np.log(10) - np.log(g)

        stddevs = self._get_stddevs(C, stddev_types, rhypo.shape[0], 
            mag_conversion_sigma=mag_conversion_sigma)

        return mean, stddevs 

def agc_mixed_004_06(envvar_prefix, path=None):
    """Load configuration

    The following steps will be undertake:
        * It will attempt to load configs from file:
          if `path` is provided, it will be used, otherwise the path
          will be taken from envvar `envvar_prefix` + "SETTINGS".
        * all envvars starting with `envvar_prefix` will be loaded.

    """
    import os
    import json

    configs = {}

    # Determine path to settings file
    settings_path = path or os.environ.get(f"{envvar_prefix}SETTINGS")
    if settings_path and os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            try:
                configs.update(json.load(f))
            except json.JSONDecodeError:
                pass

    # Load environment variables starting with prefix
    for key, value in os.environ.items():
        if key.startswith(envvar_prefix):
            # Remove prefix from the key for the config dictionary
            config_key = key[len(envvar_prefix):]
            configs[config_key] = value

    return configs
