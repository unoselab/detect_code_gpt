def hwc_mixed_005_01(self, cmd, collation=None):
        """Internal count helper."""
        with self._socket_for_reads() as (sock_info, slave_ok):
            res = self._command(
                sock_info, cmd, slave_ok,
                allowable_errors=["ns missing"],
                codec_options=self.__write_response_codec_options,
                read_concern=self.read_concern,
                collation=collation)
        if res.get("errmsg", "") == "ns missing":
            return 0
        return int(res["n"]) 

def hwc_mixed_005_02(encoder_input,
                              encoder_self_attention_bias,
                              encoder_decoder_attention_bias,
                              query,
                              hparams):
  """Iterative encoder decoder."""
  for _ in range(hparams.num_rec_steps):
    with tf.variable_scope("step", reuse=tf.AUTO_REUSE):
      encoder_output = image_question_encoder(
          encoder_input,
          encoder_self_attention_bias,
          hparams,
          query)

      decoder_output = decoder(
          query,
          encoder_output,
          None,
          encoder_decoder_attention_bias,
          hparams)

      encoder_input = encoder_output
      query = decoder_output

      return decoder_output 

async def agc_mixed_005_03(config_name: str) -> None:
    """
    Deletes created pool ledger configuration.

    :param config_name: Name of the pool ledger configuration to delete.
    :return: Error code
    """

    if not hasattr(delete_pool_ledger_config, "cb"):
        logger.debug("vcx_pool_delete_config() called")
        c_config_name = c_char_p(config_name.encode('utf-8'))

        delete_pool_ledger_config.cb = create_cb(CFUNCTYPE(None, c_uint32, c_uint32))

        error_code = await do_call('vcx_pool_delete_config',
                                   c_config_name,
                                   delete_pool_ledger_config.cb)
        check_error(error_code)

        logger.debug("vcx_pool_delete_config() completed")
        return error_code 

def agc_mixed_005_04(self):
        """
        Get a Twisted Agent that performs Client SSL authentication for Koji.
        """
        # Load "cert" into a PrivateCertificate.
        if not self.ssl_cert_path:
            raise ValueError("No SSL certificate path specified")

        if not self.ssl_key_path:
            raise ValueError("No SSL key path specified")

        if not self.ssl_ca_path:
            raise ValueError("No SSL CA path specified")

        ssl_ctx_factory = ssl.DefaultOpenSSLContextFactory(
            self.ssl_key_path, self.ssl_cert_path)

        reactor = self.reactor
        if reactor is None:
            reactor = _get_reactor()

        return Agent(reactor, ssl_ctx_factory) 

def agc_mixed_005_05(self, recursive=True, include_parent_ref=False,
                       include_defaults=False):
        """Export obj to dictionary"""
        if recursive:
            return self.export_to_dict_recursive(include_parent_ref=include_parent_ref,
                                                include_defaults=include_defaults)
        else:
            return self.export_to_dict_non_recursive(include_parent_ref=include_parent_ref,
                                                    include_defaults=include_defaults) 

def hwc_mixed_005_06(self, key, section=None, default=_onion_dict_guard):
        """Try to get the key from each dict in turn.
        If you specify the optional section it looks there first.
        """
        if section is not None:
            section_dict = self.__sections.get(section, {})
            if key in section_dict:
                return section_dict[key]
        for d in self.__dictionaries:
            if key in d:
                return d[key]
        if default is _onion_dict_guard:
            raise KeyError(key)
        else:
            return default
