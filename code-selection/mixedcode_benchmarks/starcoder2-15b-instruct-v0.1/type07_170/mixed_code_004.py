def agc_mixed_004_01(self, name, cb, request=None, notify_disconnect=False, queue=None):
        """Create a subscription.

        :param str name: PV name string
        :param callable cb: Processing callback
        :param request: A :py:class:`p4p.Value` or string to qualify this request, or None to use a default.
        :param bool notify_disconnect: In additional to Values, the callback may also be call with instances of Exception.
                                       Specifically: Disconnected , RemoteError, or Cancelled
        :param WorkQueue queue: A work queue through which monitor callbacks are dispatched.
        :returns: a :py:class:`Subscription` instance

        The callable will be invoked with one argument which is either.

        * A p4p.Value (Subject to :py:ref:`unwrap`)
        * A sub-class of Exception (Disconnected , RemoteError, or Cancelled)
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if not callable(cb):
            raise TypeError("cb must be a callable")
        if request is not None and not isinstance(request, (p4p.Value, str)):
            raise TypeError("request must be a p4p.Value or string")
        if not isinstance(notify_disconnect, bool):
            raise TypeError("notify_disconnect must be a bool")
        if queue is not None and not isinstance(queue, WorkQueue):
            raise TypeError("queue must be a WorkQueue")
        return Subscription(self, name, cb, request, notify_disconnect, queue) 

def hwc_mixed_004_02(pathpatch, z = 0, normal = 'z'):
    """
    Transforms a 2D Patch to a 3D patch using the given normal vector.

    The patch is projected into they XY plane, rotated about the origin
    and finally translated by z.
    """
    if type(normal) is str: #Translate strings to normal vectors
        index = "xyz".index(normal)
        normal = np.roll((1.0,0,0), index)

    normal /= np.linalg.norm(normal) #Make sure the vector is normalised

    path = pathpatch.get_path() #Get the path and the associated transform
    trans = pathpatch.get_patch_transform()

    path = trans.transform_path(path) #Apply the transform

    pathpatch.__class__ = art3d.PathPatch3D #Change the class
    pathpatch._code3d = path.codes #Copy the codes
    pathpatch._facecolor3d = pathpatch.get_facecolor #Get the face color

    verts = path.vertices #Get the vertices in 2D

    d = np.cross(normal, (0, 0, 1)) #Obtain the rotation vector
    M = rotation_matrix(d) #Get the rotation matrix

    pathpatch._segment3d = \
        np.array([np.dot(M, (x, y, 0)) + (0, 0, z) for x, y in verts])
    return pathpatch 

def agc_mixed_004_03(self, on=[], off=[]):
        """
        This method serves as the primary interaction point
            to the controls interface.
        - The 'on' and 'off' arguments can either be a list or a single string.
            This allows for both individual device control and batch controls.

        Note:
            Both the onlist and offlist are optional. 
            If only one item is being managed, it can be passed as a string.

        Usage:
            - Turning off all devices:
                ctrlobj.control(off="all")
            - Turning on all devices:
                ctrlobj.control(on="all")

            - Turning on the light and fan ONLY (for example)
                ctrlobj.control(on=["light", "fan"])

            - Turning on the light and turning off the fan (for example)
                ctrolobj.control(on="light", off="fan")

        """
        if isinstance(on, str):
            on = [on]
        if isinstance(off, str):
            off = [off]
        if "all" in on:
            self.turn_on_all()
        elif "all" in off:
            self.turn_off_all()
        else:
            for device in on:
                self.turn_on(device)
            for device in off:
                self.turn_off(device) 

def agc_mixed_004_04(self, context, method, routers, operation,
                      shuffle_agents):
        """Notify all or individual Cisco cfg agents."""
        if shuffle_agents:
            random.shuffle(routers)
        for router in routers:
            if operation == "add":
                self._add_cfg_agent(context, method, router)
            elif operation == "delete":
                self._delete_cfg_agent(context, method, router)
            else:
                raise ValueError(
                    "Invalid operation: {}".format(operation)
                ) 

def hwc_mixed_004_05(value=None):
        """Get the hostname of the server or set the server using hostname or aliases.
        Supported aliases: 'localhost', 'staging', 'labs'.
        Also set via environment variable GRAPHISTRY_HOSTNAME."""
        if value is None:
            return PyGraphistry._config['hostname']

        # setter
        shortcuts = {'dev': 'localhost:3000',
                     'staging': 'staging.graphistry.com',
                     'labs': 'labs.graphistry.com'}
        if value in shortcuts:
            resolved = shortcuts[value]
            PyGraphistry._config['hostname'] = resolved
            util.warn('Resolving alias %s to %s' % (value, resolved))
        else:
            PyGraphistry._config['hostname'] = value 

def hwc_mixed_004_06(obj, pretty=False):
    """
    Turn a nested object into a (compressed) JSON string.

    Parameters
    ----------
    obj : dict
        Any kind of dictionary structure.
    pretty : bool, optional
        Whether to format the resulting JSON in a more legible way (
        default False).

    """
    if pretty:
        params = dict(sort_keys=True, indent=2, allow_nan=False,
                      separators=(",", ": "), ensure_ascii=False)
    else:
        params = dict(sort_keys=False, indent=None, allow_nan=False,
                      separators=(",", ":"), ensure_ascii=False)
    try:
        return json.dumps(obj, **params)
    except (TypeError, ValueError) as error:
        LOGGER.critical(
            "The memote result structure is incompatible with the JSON "
            "standard.")
        log_json_incompatible_types(obj)
        raise_with_traceback(error)
