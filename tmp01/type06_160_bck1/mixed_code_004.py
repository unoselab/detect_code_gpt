def agc_mixed_004_01(seq_path,
                             failures,
                             output_fasta_fp):
    """ Parses seq IDs from failures list, writes to output_fasta_fp

    seq_path: filepath of original input fasta file.
    failures: list/set of failure seq IDs
    output_fasta_fp: path to write parsed sequences
    """

    seq_ids = set()
    with open(seq_path, 'r') as f:
        for line in f:
            if line[0] == '>':
                seq_id = line.strip().split()[0][1:]
                seq_ids.add(seq_id)
    with open(output_fasta_fp, 'w') as f:
        for seq_id in seq_ids:
            if seq_id in failures:
                continue
            f.write('>' + seq_id + '\n')
            f.write(seq_id + '\n') 

def agc_mixed_004_02(name, value):
    """
    Only succeed if the value in the given register location is less than
    the given value

    USAGE:

    .. code-block:: yaml

        foo:
          check.lt:
            - value: 42

        run_remote_ex:
          local.cmd:
            - tgt: '*'
            - func: test.ping
            - require:
              - check: foo
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}
    if not isinstance(value, int):
        ret["comment"] = "Value must be an integer"
        return ret
    if not isinstance(name, str):
        ret["comment"] = "Name must be a string"
        return ret
    if not isinstance(name, str):
        ret["comment"] = "Name must be a string"
        return ret
    if __salt__["reg.read_value"](name)["vdata"] < value:
        ret["result"] = True
        ret["comment"] = "Value is less than {}".format(value)
    else:
        ret["comment"] = "Value is not less than {}".format(value)
    return ret 

def hwc_mixed_004_03(self, data):
        """ Processes a received STATUS message and notifies listeners. """
        status = self._parse_status(data, self.cast_type)
        is_new_app = self.app_id != status.app_id and self.app_to_launch
        self.status = status

        self.logger.debug("Received status: %s", self.status)
        self._report_status()

        if is_new_app and self.app_to_launch == self.app_id:
            self.app_to_launch = None
            self.app_launch_event.set()
            if self.app_launch_event_function:
                self.logger.debug("Start app_launch_event_function...")
                self.app_launch_event_function()
                self.app_launch_event_function = None 

def hwc_mixed_004_04(cls, sock):
    """Parse the request (the pre-execution) section of the nailgun protocol from the given socket.

    Handles reading of the Argument, Environment, Working Directory and Command chunks from the
    client which represents the "request" phase of the exchange. Working Directory and Command are
    required and must be sent as the last two chunks in this phase. Argument and Environment chunks
    are optional and can be sent more than once (thus we aggregate them).
    """

    command = None
    working_dir = None
    arguments = []
    environment = {}

    while not all((working_dir, command)):
      chunk_type, payload = cls.read_chunk(sock)

      if chunk_type == ChunkType.ARGUMENT:
        arguments.append(payload)
      elif chunk_type == ChunkType.ENVIRONMENT:
        key, val = payload.split(cls.ENVIRON_SEP, 1)
        environment[key] = val
      elif chunk_type == ChunkType.WORKING_DIR:
        working_dir = payload
      elif chunk_type == ChunkType.COMMAND:
        command = payload
      else:
        raise cls.ProtocolError('received non-request chunk before header was fully received!')

    return working_dir, command, arguments, environment 

def hwc_mixed_004_05(self, s):
        """
        Commit the pending r/w state if it has been triggered (e.g. by an
        underlying TLSChangeCipherSpec or a SSLv2ClientMasterKey). We update
        nothing if the prcs was not set, as this probably means that we're
        working out-of-context (and we need to keep the default rcs).
        """
        if self.tls_session.triggered_prcs_commit:
            if self.tls_session.prcs is not None:
                self.tls_session.rcs = self.tls_session.prcs
                self.tls_session.prcs = None
            self.tls_session.triggered_prcs_commit = False
        if self.tls_session.triggered_pwcs_commit:
            if self.tls_session.pwcs is not None:
                self.tls_session.wcs = self.tls_session.pwcs
                self.tls_session.pwcs = None
            self.tls_session.triggered_pwcs_commit = False
        return s 

def agc_mixed_004_06(self):
        """Gets the firmware update service uri.

        :returns: firmware update service uri
        :raises: IloError, on an error from iLO.
        :raises: IloConnectionError, if not able to reach iLO.
        :raises: IloCommandNotSupportedError, for not finding the uri
        """
        try:
            return self._client.get_uri(
                '/redfish/v1/Managers/iLOService/FirmwareInventory')
        except (exception.IloConnectionError,
                exception.IloCommandNotSupportedError) as e:
            raise e
        except exception.IloError as e:
            LOG.error(_LE("Failed to get firmware update service resource "
                          "from iLO. Error: %s"), e)
            raise exception.IloError(e)
