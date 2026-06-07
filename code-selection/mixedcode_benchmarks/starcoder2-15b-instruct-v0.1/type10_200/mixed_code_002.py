def agc_mixed_002_01(self, url, engineio_path, transport):
        """Generate the Engine.IO connection URL."""
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        if scheme == 'http':
            scheme = 'ws'
        elif scheme == 'https':
            scheme = 'wss'
        netloc = parsed_url.netloc
        path = parsed_url.path
        if not path.endswith(engineio_path):
            path += engineio_path
        query = parsed_url.query
        if query:
            query += '&'
        else:
            query = '?'
        query += f'transport={transport}'
        return urlunparse((scheme, netloc, path, '', query, '')) 

def hwc_mixed_002_02(self, catalog):
        """
        Retain only the catalog objects which fall within the
        observable (i.e., unmasked) space.  NOTE: This returns a
        *selection* (i.e., objects are retained if the value of the
        output array is True).

        Parameters:
        catalog: a Catalog object
        Returns:
        sel    : boolean selection array where True means the object would be observable (i.e., unmasked).

        ADW: Careful, this function is fragile! The selection here should
             be the same as isochrone.observableFraction space. However,
             for technical reasons it is faster to do the calculation with
             broadcasting there.
        """

        # ADW: This creates a slope in color-magnitude space near the magnitude limit
        # i.e., if color=g-r then you can't have an object with g-r=1 and mag_r > mask_r-1
        # Depending on which is the detection band, this slope will appear at blue
        # or red colors. When it occurs at blue colors, it effects very few objects.
        # However, when occuring for red objects it can cut many objects. It is 
        # unclear that this is being correctly accounted for in the likelihood

        ### # Check that the objects fall in the color-magnitude space of the ROI
        ### # ADW: I think this is degenerate with the cut_cmd
        ### sel_mag = np.logical_and(catalog.mag > self.roi.bins_mag[0],
        ###                             catalog.mag < self.roi.bins_mag[-1])
        ### sel_color = np.logical_and(catalog.color > self.roi.bins_color[0],
        ###                               catalog.color < self.roi.bins_color[-1])

        # and are observable in the ROI-specific mask for both bands
        #if not hasattr(catalog, 'pixel_roi_index'): # TODO: An attempt to save computations, but not robust
        #    catalog.spatialBin(self.roi)
        catalog.spatialBin(self.roi)
        sel_roi = (catalog.pixel_roi_index >= 0) # Objects outside ROI have pixel_roi_index of -1
        sel_mag_1 = catalog.mag_1 < self.mask_1.mask_roi_sparse[catalog.pixel_roi_index]
        sel_mag_2 = catalog.mag_2 < self.mask_2.mask_roi_sparse[catalog.pixel_roi_index]

        # and are located in the region of color-magnitude space where background can be estimated
        sel_cmd = ugali.utils.binning.take2D(self.solid_angle_cmd,
                                             catalog.color, catalog.mag,
                                             self.roi.bins_color, self.roi.bins_mag) > 0.

        sel = np.all([sel_roi,sel_mag_1,sel_mag_2,sel_cmd], axis=0)
        return sel 

def hwc_mixed_002_03(hkls):
    """
    Returns unique families of Miller indices. Families must be permutations
    of each other.

    Args:
        hkls ([h, k, l]): List of Miller indices.

    Returns:
        {hkl: multiplicity}: A dict with unique hkl and multiplicity.
    """
    # TODO: Definitely can be sped up.
    def is_perm(hkl1, hkl2):
        h1 = np.abs(hkl1)
        h2 = np.abs(hkl2)
        return all([i == j for i, j in zip(sorted(h1), sorted(h2))])

    unique = collections.defaultdict(list)
    for hkl1 in hkls:
        found = False
        for hkl2 in unique.keys():
            if is_perm(hkl1, hkl2):
                found = True
                unique[hkl2].append(hkl1)
                break
        if not found:
            unique[hkl1].append(hkl1)

    pretty_unique = {}
    for k, v in unique.items():
        pretty_unique[sorted(v)[-1]] = len(v)

    return pretty_unique 

def hwc_mixed_002_04(name=None):
    """
    function takes no input and issues a RESTFUL call to get a list of custom views from HPE IMC. Optioanl Name input
    will return only the specified view.
    :param name: string containg the name of the desired custom view
    :return: list of dictionaries containing attributes of the custom views.
    """
    if auth is None or url is None:  # checks to see if the imc credentials are already available
        set_imc_creds()
    if name is None:
        get_custom_views_url = '/imcrs/plat/res/view/custom?resPrivilegeFilter=false&desc=false&total=false'
    elif name is not None:
        get_custom_views_url = '/imcrs/plat/res/view/custom?resPrivilegeFilter=false&name='+ name + '&desc=false&total=false'
    f_url = url + get_custom_views_url
    r = requests.get(f_url, auth=auth, headers=headers)  # creates the URL using the payload variable as the contents
    if r.status_code == 200:
        customviewlist = (json.loads(r.text))['customView']
        if type(customviewlist) is dict:
            customviewlist = [customviewlist]
            return customviewlist
        else:
            return customviewlist
    else:
        print(r.status_code)
        print("An Error has occured") 

def agc_mixed_002_05(self, node=None):
        """Run basic healthchecks against the current node, or against a given
        node.

            Example response:
                > {"status":"ok"}
                > {"status":"failed","reason":"string"}

        :param node: Node name

        :raises ApiError: Raises if the remote server encountered an error.
        :raises ApiConnectionError: Raises if there was a connectivity issue.

        :rtype: dict
        """
        if node is None:
            node = self.current_node
        try:
            response = self.healthcheck(node)
        except Exception as e:
            if isinstance(e, ApiError):
                raise
            elif isinstance(e, ApiConnectionError):
                raise
            else:
                raise ApiError(f"Unexpected error: {e}")
        if response["status"] == "ok":
            return response
        else:
            raise ApiError(f"Healthcheck failed: {response['reason']}") 

def agc_mixed_002_06(name, apps, exclude_packages=None, exclude_command_class=None):
    """
    Searches through the given apps to find the named command class. Skips
    over any packages specified by exclude_packages and any command class
    specified by exclude_command_class. Returns the last command class found
    or None if the command class could not be found.

    Django's command searching behavior is backwards with respect to other
    features like template and static file loaders. This function follows
    that convention.

    """
    exclude_packages = exclude_packages or []
    exclude_command_class = exclude_command_class or []

    for app in apps:
        if app.__name__ in exclude_packages:
            continue

        try:
            module = __import__(app.__name__ + '.' + name)
        except ImportError:
            continue

        for attr in dir(module):
            if attr in exclude_command_class:
                continue

            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseCommand) and obj!= BaseCommand:
                return obj

    return None
