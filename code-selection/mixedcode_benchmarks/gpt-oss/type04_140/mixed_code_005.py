def agc_mixed_005_01(string):
    """
    Find the length of the longest substring
    without repeating characters.
    Uses alternative algorithm.
    Return max_len and the substring as a tuple
    """
    start = 0
    max_len = 0
    max_sub = ""
    last_idx = {}
    for i, ch in enumerate(string):
        if ch in last_idx and last_idx[ch] >= start:
            start = last_idx[ch] + 1
        last_idx[ch] = i
        cur_len = i - start + 1
        if cur_len > max_len:
            max_len = cur_len
            max_sub = string[start:i+1]
    return max_len, max_sub 

async def hwc_mixed_005_02(self):
        """Return True if it appears we can connect to a SOCKS proxy,
        otherwise False.
        """
        if self.protocol is SOCKS4a:
            remote_address = NetAddress('www.apple.com', 80)
        else:
            remote_address = NetAddress('8.8.8.8', 53)

        sock = await self._connect_one(remote_address)
        if isinstance(sock, socket.socket):
            sock.close()
            return True

        # SOCKSFailure indicates something failed, but that we are likely talking to a
        # proxy
        return isinstance(sock, SOCKSFailure) 

def agc_mixed_005_03(self, value=None):
        """
        Fix all instances of this variable to a value if provided or to
        their current value otherwise.

        Args:
            value: value to be set.
        """

        if value is None:
            if not getattr(self, "instances", None):
                raise ValueError("No instances available to infer a value.")
            # Use the value of the first instance as the reference
            value = self.instances[0].value
        for inst in getattr(self, "instances", []):
            setattr(inst, "value", value)
            setattr(inst, "fixed", True)
        return self 

def hwc_mixed_005_04(hydrated_struct):
  target_adaptor = hydrated_struct.value
  """Construct a HydratedTarget from a TargetAdaptor and hydrated versions of its adapted fields."""
  # Hydrate the fields of the adaptor and re-construct it.
  hydrated_fields = yield [Get(HydratedField, HydrateableField, fa)
                           for fa in target_adaptor.field_adaptors]
  kwargs = target_adaptor.kwargs()
  for field in hydrated_fields:
    kwargs[field.name] = field.value
  yield HydratedTarget(target_adaptor.address,
                        TargetAdaptor(**kwargs),
                        tuple(target_adaptor.dependencies)) 

def agc_mixed_005_05(self, location):
        """
        Return the `EditorBuffer` for this location.
        When this file was not yet loaded, return None
        """
        file_path = getattr(location, "file", None)
        if file_path is None:
            # Fallback: treat location as a sequence where the first element is the path.
            try:
                file_path = location[0]
            except Exception:
                return None

        # Retrieve the buffer if it has already been loaded; otherwise return None.
        return getattr(self, "_editor_buffers", {}).get(file_path) 

def hwc_mixed_005_06(self, scopes=None, redirect_uri=None):
        """
        Generates a url to send users so that they may authenticate to this
        application.  This url is suitable for redirecting a user to.  For
        example, in `Flask`_, a login route might be implemented like this::

           @app.route("/login")
           def begin_oauth_login():
               login_client = LinodeLoginClient(client_id, client_secret)
               return redirect(login_client.generate_login_url())

        .. _Flask:: http://flask.pocoo.org

        :param scopes: The OAuth scopes to request for this login.
        :type scopes: list
        :param redirect_uri: The requested redirect uri.  The login service
                             enforces that this is under the registered redirect
                             path.
        :type redirect_uri: str

        :returns: The uri to send users to for this login attempt.
        :rtype: str
        """
        url = self.base_url + "/oauth/authorize"
        split = list(urlparse(url))
        params = {
            "client_id": self.client_id,
            "response_type": "code", # needed for all logins
        }
        if scopes:
            params["scopes"] = OAuthScopes.serialize(scopes)
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        split[4] = urlencode(params)
        return urlunparse(split)
