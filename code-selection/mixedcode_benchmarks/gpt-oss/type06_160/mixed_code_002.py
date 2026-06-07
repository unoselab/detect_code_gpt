def agc_mixed_002_01(rootdir):
    """Sometimes, we want to use this tool with non-git repositories.
    This function allows us to do so.
    """
    import os
    from pathlib import Path

    root_path = Path(rootdir)
    if not root_path.is_dir():
        return []

    ignored_dirs = {'.git', '.hg', '.svn', '__pycache__'}

    files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # modify dirnames in-place to skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
        for name in filenames:
            file_path = Path(dirpath) / name
            # store path relative to the root directory
            files.append(str(file_path.relative_to(root_path)))
    return sorted(files) 

def hwc_mixed_002_02(self, X, lenscale=None):
        r"""
        Get the gradients of this basis w.r.t.\ the length scales.

        Parameters
        ----------
        X: ndarray
            (N, d) array of observations where N is the number of samples, and
            d is the dimensionality of X.
        lenscale: scalar or ndarray, optional
            scalar or array of shape (d,) length scales (one for each dimension
            of X). If not input, this uses the value of the initial length
            scale.

        Returns
        -------
        ndarray:
            of shape (N, 2*nbases[, d]) where d is number of lenscales (if not
            ARD, i.e. scalar lenscale, this is just a 2D array). This is
            :math:`\partial \Phi(\mathbf{X}) / \partial \mathbf{l}`
        """
        N, D = X.shape
        lenscale = self._check_dim(D, lenscale)[:, np.newaxis]

        WX = np.dot(X, self.W / lenscale)
        sinWX = - np.sin(WX)
        cosWX = np.cos(WX)

        dPhi = []
        for i, l in enumerate(lenscale):
            dWX = np.outer(X[:, i], - self.W[i, :] / l**2)
            dPhi.append(np.hstack((dWX * sinWX, dWX * cosWX)) /
                        np.sqrt(self.n))

        return np.dstack(dPhi) if len(lenscale) != 1 else dPhi[0] 

def hwc_mixed_002_03(json_string, object_type, mappers):
    """
    This function will use the custom JsonDecoder and the conventions.mappers to recreate your custom object
    in the parse json string state just call this method with the json_string your complete object_type and with your
    mappers dict.
    the mappers dict must contain in the key the object_type (ex. User) and the value will contain a method that get
    key, value (the key will be the name of the object property we like to parse and the value
    will be the properties of the object)
    """
    obj = json.loads(json_string, cls=JsonDecoder, object_mapper=mappers.get(object_type, None))

    if obj is not None:
        try:
            obj = object_type(**obj)
        except TypeError:
            initialize_dict, set_needed = Utils.make_initialize_dict(obj, object_type.__init__)
            o = object_type(**initialize_dict)
            if set_needed:
                for key, value in obj.items():
                    setattr(o, key, value)
            obj = o
    return obj 

def agc_mixed_002_04(self, thing=None, **kwargs):
        """
        Constructs a new simulation manager.

        :param thing:           Optional - What to put in the new SimulationManager's active stash (either a SimState or a list of SimStates).
        :param kwargs:          Any additional keyword arguments will be passed to the SimulationManager constructor
        :returns:               The new SimulationManager
        :rtype:                 angr.sim_manager.SimulationManager

        Many different types can be passed to this method:

        * If nothing is passed in, the SimulationManager is seeded with a state initialized for the program
          entry point, i.e. :meth:`entry_state()`.
        * If a :class:`SimState` is passed in, the SimulationManager is seeded with that state.
        * If a list is passed in, the list must contain only SimStates and the whole list will be used to seed the SimulationManager.
        """
        from angr import SimState, SimulationManager

        if thing is None:
            init_state = self.entry_state()
        elif isinstance(thing, SimState):
            init_state = thing
        elif isinstance(thing, (list, tuple)):
            if not all(isinstance(s, SimState) for s in thing):
                raise TypeError("All elements in the list must be SimState instances")
            init_state = list(thing)
        else:
            raise 

def agc_mixed_002_05(self, state, data):
        """Split data into a sequence of frames."""

        # Pull in any partially-processed data
        buf = state.setdefault('buffer', bytearray())
        buf.extend(data)
        frames = []
        while True:
            if len(buf) < 4:
                break
            length = int.from_bytes(buf[:4], 'big')
            if len(buf) < 4 + length:
                break
            frames.append(bytes(buf[4:4 + length]))
            del buf[:4 + length]
        return frames 

def hwc_mixed_002_06(self, block=False):
        """
        Kill the daemon process.

        Sends the SIGKILL signal to the daemon process, killing it. You
        probably want to try :py:meth:`stop` first.

        If ``block`` is true then the call blocks until the daemon
        process has exited. ``block`` can either be ``True`` (in which
        case it blocks indefinitely) or a timeout in seconds.

        Returns ``True`` if the daemon process has (already) exited and
        ``False`` otherwise.

        The PID file is always removed, whether the process has already
        exited or not. Note that this means that subsequent calls to
        :py:meth:`is_running` and :py:meth:`get_pid` will behave as if
        the process has exited. If you need to be sure that the process
        has already exited, set ``block`` to ``True``.

        .. versionadded:: 0.5.1
            The ``block`` parameter
        """
        pid = self.get_pid()
        if not pid:
            raise ValueError('Daemon is not running.')
        try:
            os.kill(pid, signal.SIGKILL)
            return _block(lambda: not self.is_running(), block)
        except OSError as e:
            if e.errno == errno.ESRCH:
                raise ValueError('Daemon is not running.')
            raise
        finally:
            self.pid_file.release()
