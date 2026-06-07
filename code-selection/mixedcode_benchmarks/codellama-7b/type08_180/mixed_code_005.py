def hwc_mixed_005_01(self, corpus_id):
        """Return updated belief scores for a given corpus.

        Parameters
        ----------
        corpus_id : str
            The ID of the corpus for which beliefs are to be updated.

        Returns
        -------
        dict
            A dictionary of belief scores with keys corresponding to Statement
            UUIDs and values to new belief scores.
        """
        corpus = self.get_corpus(corpus_id)
        be = BeliefEngine(self.scorer)
        stmts = list(corpus.statements.values())
        be.set_prior_probs(stmts)
        # Here we set beliefs based on actual curation
        for uuid, correct in corpus.curations.items():
            stmt = corpus.statements.get(uuid)
            if stmt is None:
                logger.warning('%s is not in the corpus.' % uuid)
                continue
            stmt.belief = correct
        belief_dict = {st.uuid: st.belief for st in stmts}
        return belief_dict 

def hwc_mixed_005_02(self):
    """Starts gdb and attempts to auto-load symbol file (unless turned off).

    Raises:
      GdbProcessError: if gdb is already running
    """
    if self.attached:
      raise GdbProcessError('Gdb is already running.')
    self._gdb = GdbProxy(arch=self.arch)
    self._gdb.Attach(self.position)

    if self.auto_symfile_loading:
      try:
        self.LoadSymbolFile()
      except (ProxyError, TimeoutError) as err:
        self._gdb = GdbProxy(arch=self.arch)
        self._gdb.Attach(self.position)
        if not self.gdb.IsSymbolFileSane(self.position):
          logging.warning('Failed to automatically load a sane symbol file, '
                          'most functionality will be unavailable until symbol'
                          'file is provided.')
          logging.debug(err.message) 

def agc_mixed_005_03(self, string_version=None):
        """
        Check that the version information is consistent with the VCS
        before doing a release. If supplied with a string version,
        this is also checked against the current version. Should be
        called from setup.py with the declared package version before
        releasing to PyPI.
        """
        if string_version is not None:
            if string_version != self.version:
                raise ValueError(
                    "Version mismatch: %s != %s" % (string_version, self.version)
                )
        if self.vcs is None:
            raise RuntimeError("No VCS found")
        if self.vcs.get_version() != self.version:
            raise RuntimeError(
                "Version mismatch: %s != %s" % (self.vcs.get_version(), self.version)
            ) 

def agc_mixed_005_04(input_value):
        """Recursively serialize task input list"""
        if isinstance(input_value, list):
            return [_serialize_input_list(x) for x in input_value]
        elif isinstance(input_value, dict):
            return {k: _serialize_input_list(v) for k, v in input_value.items()}
        elif isinstance(input_value, str):
            return input_value
        elif isinstance(input_value, (int, float)):
            return str(input_value)
        elif isinstance(input_value, bool):
            return str(input_value).lower()
        elif input_value is None:
            return None
        else:
            raise TypeError(f"Unsupported input type: {type(input_value)}") 

def hwc_mixed_005_05(kind, device, channels, dtype, latency, samplerate):
    """Generate PaStreamParameters struct."""
    if device is None:
        if kind == 'input':
            device = _pa.Pa_GetDefaultInputDevice()
        elif kind == 'output':
            device = _pa.Pa_GetDefaultOutputDevice()

    info = device_info(device)
    if channels is None:
        channels = info['max_' + kind + '_channels']
    dtype = np.dtype(dtype)
    try:
        sample_format = _np2pa[dtype]
    except KeyError:
        raise ValueError("Invalid " + kind + " sample format")
    if samplerate is None:
        samplerate = info['default_samplerate']
    parameters = ffi.new(
        "PaStreamParameters*",
        (device, channels, sample_format, latency, ffi.NULL))
    return parameters, dtype, samplerate 

def agc_mixed_005_06(frame):
    """Return info about frame.

    Keyword arg:
        frame

    Return string in format:

    File {file name}, line {line number}, in 
    {name of parent of code object} {newline}
    Line from file at line number
    """

    if frame.f_code.co_filename == "<string>":
        return "File {file name}, line {line number}, in {name of parent of code object}\n{line from file at line number}".format(
            file_name=frame.f_code.co_filename,
            line_number=frame.f_lineno,
            name_of_parent_of_code_object=frame.f_code.co_name,
            line_from_file_at_line_number=frame.f_code.co_firstlineno,
        )
    else:
        return "File {file name}, line {line number}, in {name of parent of code object}\n{line from file at line number}".format(
            file_name=frame.f_code.co_filename,
            line_number=frame.f_lineno,
            name_of_parent_of_code_object=frame.f_code.co_name,
            line_from_file_at_line_number=frame.f_code.co_firstlineno,
        )
