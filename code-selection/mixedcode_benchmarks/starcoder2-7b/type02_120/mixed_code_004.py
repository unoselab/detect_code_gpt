def agc_mixed_004_01(self, sites):
        """
        Return delta's for equation 4
        delta_C = 1 for site class C (360<=Vs30<760), 0 otherwise
        delta_D = 1 for site class D (Vs30<=360), 0 otherwise
        """
        delta_C = np.zeros(len(sites))
        delta_D = np.zeros(len(sites))
        for i, site in enumerate(sites):
            if site.vs30 >= 360:
                delta_D[i] = 1
            if 360 <= site.vs30 < 760:
                delta_C[i] = 1
        return delta_C, delta_D 

def agc_mixed_004_02(self):
        """Attempt to reset our connection state for a new request/response
        cycle.

        If both client and server are in :data:`DONE` state, then resets them
        both to :data:`IDLE` state in preparation for a new request/response
        cycle on this same connection. Otherwise, raises a
        :exc:`LocalProtocolError`.

        See :ref:`keepalive-and-pipelining`.

        """
        if self.client_state == self.DONE and self.server_state == self.DONE:
            self.client_state = self.server_state = self.IDLE
        else:
            raise LocalProtocolError(
                "Cannot start a new request/response cycle on a connection "
                "that is not in the DONE state."
            ) 

def hwc_mixed_004_03(self, src, strings):
    """Injects languages into (potentially) template strings."""
    if src not in self.sources:
      raise ValueError("Invalid source for '{0}': {1}".format(self.name, src))
    def _format_string(s):
      if "{0}" in s and "{1}" and "{src}" in s:
        return s.format(*sorted([src, self.target]), src=src)
      elif "{0}" in s and "{1}" in s:
        return s.format(*sorted([src, self.target]))
      elif "{src}" in s:
        return s.format(src=src)
      else:
        return s
    return [_format_string(s) for s in strings] 

def hwc_mixed_004_04(kwargs=None, conn=None, call=None):
    """
    .. versionadded:: 2015.8.0

    Return information about a management_certificate

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_management_certificate my-azure name=my_management_certificate \\
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    """
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_management_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if kwargs is None:
        kwargs = {}

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    data = conn.get_management_certificate(kwargs['thumbprint'])
    return object_to_dict(data) 

def hwc_mixed_004_05(world, tibiadata, json):
    """Displays the list of guilds for a specific world"""
    world = " ".join(world)
    guilds = _fetch_and_parse(ListedGuild.get_world_list_url, ListedGuild.list_from_content,
                              ListedGuild.get_world_list_url_tibiadata, ListedGuild.list_from_tibiadata,
                              tibiadata, world)
    if json and guilds:
        import json as _json
        print(_json.dumps(guilds, default=dict, indent=2))
        return
    print(get_guilds_string(guilds)) 

def agc_mixed_004_06(self, line_str):
        """Split line and check number of columns"""
        line = line_str.split()
        if len(line)!= self.n_cols:
            raise ValueError(
                "Line {} has {} columns, but {} are expected".format(
                    line_str, len(line), self.n_cols
                )
            )
        return line
