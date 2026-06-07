def agc_mixed_003_01(self, val, info):
      """ Serialize an object """
      if info is None:
          info = set()
      # Primitive types
      if val is None or isinstance(val, (bool, int, float, str)):
          return val
      # Prevent infinite recursion on circular references
      obj_id = id(val)
      if obj_id in info:
          return '<circular>'
      info.add(obj_id)
      # Dictionaries
      if isinstance(val, dict):
          return {self.SerializeFaultDetail(k, info): self.SerializeFaultDetail(v, info) for k, v in val.items()}
      # Iterables (list 

def hwc_mixed_003_02(self, scapy_all):
        """Call scapy.all.sniff to extract PCAP files."""
        # if not self._flag_a:
        #     self._flag_a = True
        #     warnings.warn(f"'Extractor(engine=scapy)' object is not iterable; "
        #                     "so 'auto=False' will be ignored", AttributeWarning, stacklevel=stacklevel())

        if self._exlyr != 'None' or self._exptl != 'null':
            warnings.warn("'Extractor(engine=scapy)' does not support protocol and layer threshold; "
                          f"'layer={self._exlyr}' and 'protocol={self._exptl}' ignored",
                          AttributeWarning, stacklevel=stacklevel())

        # extract & analyse file
        self._expkg = scapy_all
        self._extmp = iter(scapy_all.sniff(offline=self._ifnm))

        # start iteration
        self.record_frames() 

async def hwc_mixed_003_03(self, name, change_type, change_info=None, directed_client=None):
        """Notify updates on a service to anyone who cares."""

        for monitor in self._monitors:
            try:
                result = monitor(name, change_type, change_info, directed_client=directed_client)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # We can't allow any exceptions in a monitor routine to break the server.
                self._logger.warning("Error calling monitor with update %s", name, exc_info=True) 

def agc_mixed_003_04(self, prompt):
        """Update driver based on new prompt."""
        self._last_prompt = prompt
        if hasattr(self, "driver"):
            updater = getattr(self.driver, "update", None)
            if callable(updater):
                try:
                    return updater(prompt)
                except Exception as exc:
                    raise RuntimeError(f"Failed to update driver: {exc}") from exc
        return None 

def agc_mixed_003_05(approximant_strs):
    """Parses a list of strings specifying an approximant and where that
    approximant should be used into a list that can be understood by
    FieldArray.parse_boolargs.

    Parameters
    ----------
    apprxstr : (list of) string(s)
        The strings to parse. Each string should be formatted `APPRX:COND`,
        where `APPRX` is the approximant and `COND` is a string specifying
        where it should be applied (see `FieldArgs.parse_boolargs` for examples
        of conditional strings). The last string in the list may exclude a
        conditional argument, which is the same as specifying ':else'.

    Returns
    -------
    boolargs : list
        A list of tuples giving the approximant and where to apply them. This
        can be passed directly to `FieldArray.parse_boolargs`.
    """
    if isinstance(approximant_strs, str):
        approximant_strs = [approximant_strs]
    boolargs = []
    for i, s in enumerate(approximant_strs):
        s = s.strip()
        if ':' in s:
            apprx, cond = s.split(':', 1)
            apprx = apprx.strip()
            cond = cond.strip() or 'else'
        else:
            apprx = s
            cond = 'else'
        boolargs.append((apprx, cond))
    return boolargs 

def hwc_mixed_003_06(self, raw):
        """Return an Ethernet object reconstructed from raw bytes, or an
        Exception if we can't resurrect the packet."""
        if len(raw) < Ethernet._MINLEN:
            raise NotEnoughDataError("Not enough bytes ({}) to reconstruct an "
                "Ethernet object".format(len(raw)))
        dst,src,ethertype = struct.unpack(Ethernet._PACKFMT, 
            raw[:Ethernet._MINLEN])
        self.src = src
        self.dst = dst
        if ethertype <= 1500:
            self.ethertype = EtherType.NoType
        else:
            self.ethertype = ethertype
        return raw[Ethernet._MINLEN:]
