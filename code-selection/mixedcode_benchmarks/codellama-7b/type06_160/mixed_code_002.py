def agc_mixed_002_01(source=None, source_hash=None,
                              sources=None, source_hashes=None):
    """
    Silly little function to give us a standard tuple list for sources and
    source_hashes
    """
    if source and sources:
        raise CommandExecutionError(
            "Only one of source or sources should be specified."
        )
    if source_hash and source_hashes:
        raise CommandExecutionError(
            "Only one of source_hash or source_hashes should be specified."
        )
    if source:
        sources = [source]
        source_hashes = [source_hash]
    if source_hashes is None:
        source_hashes = []
    if sources is None:
        sources = []
    return sources, source_hashes 

def hwc_mixed_002_02(self):
        # type: () -> bytes
        """
        A method to generate a string representing this El Torito Entry.

        Parameters:
         None.
        Returns:
         String representing this El Torito Entry.
        """
        if not self._initialized:
            raise pycdlibexception.PyCdlibInternalError('El Torito Entry not yet initialized')

        return struct.pack(self.FMT, self.boot_indicator, self.boot_media_type,
                           self.load_segment, self.system_type, 0,
                           self.sector_count, self.load_rba,
                           self.selection_criteria_type,
                           self.selection_criteria) 

def agc_mixed_002_03(self, segment, overwrite=False):
        """Add segments by ascending address.

        """

        if not isinstance(segment, Segment):
            raise TypeError("segment must be a Segment")

        if segment.start in self:
            if not overwrite:
                raise ValueError("segment already exists")
            self.remove(segment.start)

        if segment.start in self:
            raise ValueError("segment already exists")

        if segment.end in self:
            raise ValueError("segment already exists")

        self._segments.append(segment)
        self._segments.sort(key=lambda x: x.start) 

def hwc_mixed_002_04(self,
                       user,
                       currentPassword,
                       newPassword):
        """Change the password of a user."""
        return self.__post('/api/updatePassword',
                           data={
                               'user': user,
                               'currentPassword': currentPassword,
                               'newPassword': newPassword
                           }) 

def agc_mixed_002_05(self, httptype=None,
                             channel=None, path_file=None):
        """
        Params:

            path_file - path to output file
            channel: - integer
            httptype - type string (singlepart or multipart)

                singlepart: HTTP content is a continuos flow of audio packets
                multipart: HTTP content type is multipart/x-mixed-replace, and
                           each audio packet ends with a boundary string

        """
        if not path_file:
            raise ValueError("path_file is required")

        if not channel:
            raise ValueError("channel is required")

        if not httptype:
            raise ValueError("httptype is required")

        if httptype == "singlepart":
            self.stream_capture_singlepart(path_file, channel)
        elif httptype == "multipart":
            self.stream_capture_multipart(path_file, channel)
        else:
            raise ValueError("httptype must be singlepart or multipart") 

def hwc_mixed_002_06(self, reference: Optional[Path], repo: str) -> Optional[Path]:
        """
        Returns a repository to use in clone command, if there is one to be referenced.
        Either provided by the user of generated from already cloned branches (master is preferred).

        :param reference: Path to a local repository provided by the user or None.
        :param repo: Reference for which remote repository.
        """
        if reference is not None:
            return reference.absolute()

        repo_path = self.get_path_to_repo(repo)

        if not repo_path.exists():
            return None

        master = repo_path / "master"

        if master.exists() and master.is_dir():
            return master

        for existing_branch in repo_path.iterdir():
            if not existing_branch.is_dir():
                continue

            return existing_branch.resolve()

        return None
