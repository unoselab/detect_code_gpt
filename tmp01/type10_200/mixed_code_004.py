def agc_mixed_004_01(kind, device, channels, dtype, latency, samplerate):
    """Generate PaStreamParameters struct."""
    if kind == "input":
        stream_parameters = pa.StreamParameters(
            device=device,
            channel_count=channels,
            sample_format=dtype,
            suggested_latency=latency,
            host_api_specific_stream_info=None,
        )
    elif kind == "output":
        stream_parameters = pa.StreamParameters(
            device=device,
            channel_count=channels,
            sample_format=dtype,
            suggested_latency=latency,
            host_api_specific_stream_info=None,
        )
    else:
        raise ValueError("kind must be 'input' or 'output'")
    return stream_parameters 

def hwc_mixed_004_02(self, ip_addr):
        """
        Do reverse lookup on an ip address
        """
        # Handle silly fake ipv6 addresses
        try:
            if ip_addr[:7] == '::ffff:':
                ip_addr = ip_addr[7:]
        except TypeError:
            pass

        if ip_addr[0] in string.letters:
            return ip_addr

        try:
            return self.hostsmap[ip_addr]
        except KeyError:
            pass

        try:
            name = socket.gethostbyaddr(ip_addr)[0]
        except socket.error:
            name = ip_addr

        self.hostsmap[ip_addr] = name
        return name 

def hwc_mixed_004_03(self, module, encoding):
        """Handles encoding and delayed nodes after a module has been built"""
        module.file_encoding = encoding
        self._manager.cache_module(module)
        # post tree building steps after we stored the module in the cache:
        for from_node in module._import_from_nodes:
            if from_node.modname == "__future__":
                for symbol, _ in from_node.names:
                    module.future_imports.add(symbol)
            self.add_from_names_to_locals(from_node)
        # handle delayed assattr nodes
        for delayed in module._delayed_assattr:
            self.delayed_assattr(delayed)

        # Visit the transforms
        if self._apply_transforms:
            module = self._manager.visit_transforms(module)
        return module 

def agc_mixed_004_04(self):
        """Initializes a connection to the smtp server

        :return: True on success, False otherwise
        """
        if self.connected:
            return True
        try:
            self.smtp = smtplib.SMTP(self.host, self.port)
            self.smtp.ehlo()
            if self.tls:
                self.smtp.starttls()
                self.smtp.ehlo()
            if self.user:
                self.smtp.login(self.user, self.password)
            self.connected = True
        except Exception as e:
            self.connected = False
            raise e
        return self.connected 

def agc_mixed_004_05(self, enabled):
        """Update the UI when the user toggles the bookmarks radiobutton.

        :param enabled: The status of the radiobutton.
        :type enabled: bool
        """
        if enabled:
            self.hazard_exposure_bookmark_button.setEnabled(True)
            self.hazard_exposure_bookmark_button.setChecked(True)
            self.hazard_exposure_bookmark_button.setText("Remove Bookmark")
            self.hazard_exposure_bookmark_button.setIcon(
                self.style().standardIcon(QStyle.SP_DialogDiscardButton)
            )
            self.hazard_exposure_bookmark_button.setToolTip("Remove Bookmark")
        else:
            self.hazard_exposure_bookmark_button.setEnabled(True)
            self.hazard_exposure_bookmark_button.setChecked(False)
            self.hazard_exposure_bookmark_button.setText("Add Bookmark")
            self.hazard_exposure_bookmark_button.setIcon(
                self.style().standardIcon(QStyle.SP_DialogApplyButton)
            )
            self.hazard_exposure_bookmark_button.setToolTip("Add Bookmark") 

def hwc_mixed_004_06(self, parser_mediator, file_object):
    """Parses a bencoded file-like object.

    Args:
      parser_mediator (ParserMediator): mediates interactions between parsers
          and other components, such as storage and dfvfs.
      file_object (dfvfs.FileIO): a file-like object.

    Raises:
      UnableToParseFile: when the file cannot be parsed.
    """
    file_object.seek(0, os.SEEK_SET)
    header = file_object.read(2)
    if not self.BENCODE_RE.match(header):
      raise errors.UnableToParseFile('Not a valid Bencoded file.')

    file_object.seek(0, os.SEEK_SET)
    try:
      data_object = bencode.bdecode(file_object.read())

    except (IOError, bencode.BTFailure) as exception:
      raise errors.UnableToParseFile(
          '[{0:s}] unable to parse file: {1:s} with error: {2!s}'.format(
              self.NAME, parser_mediator.GetDisplayName(), exception))

    if not data_object:
      raise errors.UnableToParseFile(
          '[{0:s}] missing decoded data for file: {1:s}'.format(
              self.NAME, parser_mediator.GetDisplayName()))

    for plugin in self._plugins:
      try:
        plugin.UpdateChainAndProcess(parser_mediator, data=data_object)
      except errors.WrongBencodePlugin as exception:
        logger.debug('[{0:s}] wrong plugin: {1!s}'.format(
            self.NAME, exception))
