def hwc_mixed_005_01(self):
        """:obj:`CameraIntrinsics` : The camera intrinsics for the Kinect's IR camera.
        """
        if self._device is None:
            raise RuntimeError('Kinect2 device %s not runnning. Cannot return IR intrinsics')
        camera_params = self._device.getIrCameraParams()
        return CameraIntrinsics(self._ir_frame, camera_params.fx, camera_params.fy,
                                camera_params.cx, camera_params.cy,
                                height=Kinect2Sensor.DEPTH_IM_HEIGHT,
                                width=Kinect2Sensor.DEPTH_IM_WIDTH) 

def hwc_mixed_005_02(self, url):
        """Remove passed url from a binder
        """

        root = self.etree
        t_urls = root.find('urls')

        if not t_urls:
            return False

        for t_url in t_urls.findall('url'):
            if t_url.text == url.strip():
                t_urls.remove(t_url)
                if url in self.urls:
                    self.urls.remove(url)
                return True

        return False 

def agc_mixed_005_03(segID, N, CA, C, O, geo):
    """Creates a Threonine residue"""
    ##R-Group
    import numpy as np

    def _place_atom(a, b, c, length, angle_deg, dihedral_deg):
        """Place a new atom D given three previous atoms A, B, C.

        a, b, c: np.ndarray of shape (3,) – positions of atoms A, B, C
        length: bond length |C‑D|
        angle_deg: bond angle ∠B‑C‑D in degrees
        dihedral_deg: dihedral angle ∠A‑B‑C‑D in degrees
        """
        # vectors
        bc = b - c
        bc_norm = bc / np.linalg.norm(bc)

        # normal to the plane defined by (a,b,c) 

def hwc_mixed_005_04(request):
    """
    Put the selected site ID into the session - posted to from
    the "Select site" drop-down in the header of the admin. The
    site ID is then used in favour of the current request's
    domain in ``yacms.core.managers.CurrentSiteManager``.
    """
    site_id = int(request.GET["site_id"])
    if not request.user.is_superuser:
        try:
            SitePermission.objects.get(user=request.user, sites=site_id)
        except SitePermission.DoesNotExist:
            raise PermissionDenied
    request.session["site_id"] = site_id
    admin_url = reverse("admin:index")
    next = next_url(request) or admin_url
    # Don't redirect to a change view for an object that won't exist
    # on the selected site - go to its list view instead.
    if next.startswith(admin_url):
        parts = next.split("/")
        if len(parts) > 4 and parts[4].isdigit():
            next = "/".join(parts[:4])
    return redirect(next) 

def agc_mixed_005_05(str1, s2):
    """
    Distance between two strings
    """
    if not str1:
        return len(s2)
    if not s2:
        return len(str1)
    prev = list(range(len(s2) + 1))
    for i, ch1 in enumerate(str1, 1):
        cur = [i] + [0] * len(s2)
        for j, ch2 in enumerate(s2, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            repl = prev[j - 1] + (ch1 != ch2)
            cur[j] = min(ins, dele, repl)
        prev = cur
    return prev[-1] 

def agc_mixed_005_06(self, proxy, **proxy_kwargs):
        """Called to initialize the HTTPAdapter when a proxy is used."""
        if not proxy:
            raise ValueError("Proxy must be provided.")
        if proxy not in self.proxy_manager:
            proxy_headers = self.proxy_headers(proxy)
            self.proxy_manager[proxy] = self.proxy_manager_cls(
                proxy_url=proxy,
                **proxy_kwargs,
                **self.proxy_manager_kwargs,
                headers=proxy_headers,
            )
        return self.proxy_manager[proxy]
