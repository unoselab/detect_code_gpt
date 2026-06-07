def agc_mixed_002_01(self, hyperparameters):
        """Set new hyperparameters.

        Only the specified hyperparameters are modified, so any other
        hyperparameter keeps the value that had been previously given.

        If necessary, a new instance of the primitive is created.

        Args:
            hyperparameters (dict): Dictionary containing as keys the name
                                    of the hyperparameters and as values
                                    the values to be used.
        """
        for key, value in hyperparameters.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = value
                if key in self.primitive_instance.hyperparameters:
                    self.primitive_instance.hyperparameters[key] = value
            else:
                raise ValueError("Unknown hyperparameter: %s" % key)

        if self.primitive_instance is not None:
            self.primitive_instance.set_hyperparameters(self.hyperparameters) 

def hwc_mixed_002_02(self, callback, data):
        """Execute the callback in another thread. Wait for and return the results."""
        web_client = WebClient(
            token=self.token, base_url=self.base_url, ssl=self.ssl, proxy=self.proxy
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Execute the callback on a separate thread,
            future = executor.submit(
                callback, rtm_client=self, web_client=web_client, data=data
            )

            while future.running():
                pass

            future.result() 

def hwc_mixed_002_03(ab, c):
    """
    point_on_line((a,b), c) yields True if point x is on line (a,b) and False otherwise.
    """
    (a,b) = ab
    abc = [np.asarray(u) for u in (a,b,c)]
    if any(len(u.shape) == 2 for u in abc): (a,b,c) = [np.reshape(u,(len(u),-1)) for u in abc]
    else:                                   (a,b,c) = abc
    vca = a - c
    vcb = b - c
    uba = czdivide(vba, np.sqrt(np.sum(vba**2, axis=0)))
    uca = czdivide(vca, np.sqrt(np.sum(vca**2, axis=0)))
    return (np.isclose(np.sqrt(np.sum(vca**2, axis=0)), 0) |
            np.isclose(np.sqrt(np.sum(vcb**2, axis=0)), 0) |
            np.isclose(np.abs(np.sum(uba*uca, axis=0)), 1)) 

def hwc_mixed_002_04(self, target, target2=None, modifiers=""):
        """ Performs a dragDrop operation.

        Holds down the mouse button on ``dragFrom``, moves the mouse to ``dragTo``, and releases
        the mouse button.

        ``modifiers`` may be a typeKeys() compatible string. The specified keys will be held
        during the drag-drop operation.
        """
        if modifiers != "":
            keyboard.keyDown(modifiers)

        if target2 is None:
            dragFrom = self._lastMatch
            dragTo = target
        else:
            dragFrom = target
            dragTo = target2

        self.drag(dragFrom)
        time.sleep(Settings.DelayBeforeDrag)
        self.dropAt(dragTo)

        if modifiers != "":
            keyboard.keyUp(modifiers) 

def agc_mixed_002_05(self, directories_paths_and_digests):
    """Creates the specified directories on the file system.

    :param directories_paths_and_digests tuple<DirectoryToMaterialize>: Tuple of the path and
           digest of the directories to materialize.
    :returns: Nothing or an error.
    """
    # Ensure there isn't more than one of the same directory paths and paths do not have the same prefix.
    for directory_to_materialize in directories_paths_and_digests:
        directory_path = directory_to_materialize.path
        directory_digest = directory_to_materialize.digest
        try:
            self._materialize_directory(directory_path, directory_digest)
        except Exception as e:
            return Failure(
                "Failed to materialize directory {directory_path}: {error}".format(
                    directory_path=directory_path, error=e
                )
            )

    return Success() 

def agc_mixed_002_06(dir_or_filelist, pattern='*'):
    """
    If given a path to a directory, finds files recursively,
    e.g. all *.txt files in a given directory (or its subdirectories).
    If given a list of files, yields all of the files that match the given
    pattern.

    adapted from: http://stackoverflow.com/a/2186673
    """
    if isinstance(dir_or_filelist, list):
        for f in dir_or_filelist:
            if os.path.isfile(f):
                if fnmatch.fnmatch(f, pattern):
                    yield f
    else:
        for root, dirs, files in os.walk(dir_or_filelist):
            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    yield os.path.join(root, f)
