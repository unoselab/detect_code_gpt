def hwc_mixed_004_01(parent):
    """ we have to check the cls_node without changing it.
        There are two possiblities:
          1)  clsdef => suite => simple_stmt => expr_stmt => Leaf('__meta')
          2)  clsdef => simple_stmt => expr_stmt => Leaf('__meta')
    """
    for node in parent.children:
        if node.type == syms.suite:
            return has_metaclass(node)
        elif node.type == syms.simple_stmt and node.children:
            expr_node = node.children[0]
            if expr_node.type == syms.expr_stmt and expr_node.children:
                left_side = expr_node.children[0]
                if isinstance(left_side, Leaf) and \
                        left_side.value == '__metaclass__':
                    return True
    return False 

def agc_mixed_004_02(cls, name):
        """Load a parsed name from a string.

        Raises:
            TypeError: when name isn't a type of `six.string_types`.
            ValueError: when name is empty or None.
        """
        import importlib
        import six

        if not isinstance(name, six.string_types):
            raise TypeError(f"name must be a string, got {type(name).__name__}")
        if not name or not name.strip():
            raise ValueError("name must be a non‑empty string")

        name = name.strip()
        if "." in name:
            module_path, attr = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, attr)
        else:
            return importlib.import_module(name) 

def agc_mixed_004_03(s, hex_format=False):
    """ s is in hex or binary format
    """
    import hashlib

    # Determine input type and convert to bytes if needed
    if isinstance(s, str):
        # Assume hex representation
        try:
            data = bytes.fromhex(s)
        except ValueError:
            raise ValueError("String input must be valid hex")
    elif isinstance(s, (bytes, bytearray, memoryview)):
        data = bytes(s)
    else:
        raise TypeError("Input must be hex string or binary data")

    # Perform SHA-256
    sha256_hash = hashlib.sha256(data).digest()

    # Perform RIPEMD-160 on the SHA-256 result
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(sha256_hash)
    result = ripemd160.digest()

    return result.hex() if hex_format else result 

def hwc_mixed_004_04(self, rho, T):
        """Ideal gas properties"""
        rhoc = self._constants.get("rhoref", self.rhoc)
        Tc = self._constants.get("Tref", self.Tc)
        delta = rho/rhoc
        tau = Tc/T
        ideal = self._phi0(tau, delta)
        fio = ideal["fio"]
        fiot = ideal["fiot"]
        fiott = ideal["fiott"]

        propiedades = _fase()
        propiedades.h = self.R*T*(1+tau*fiot)
        propiedades.s = self.R*(tau*fiot-fio)
        propiedades.cv = -self.R*tau**2*fiott
        propiedades.cp = self.R*(-tau**2*fiott+1)
        propiedades.alfap = 1/T
        propiedades.betap = rho
        return propiedades 

def agc_mixed_004_05(cls, fd):
        """ Returns a case object from the given PSAT data file.
        """
        import ast, json

        content = fd.read()
        # Try JSON format first
        try:
            data = json.loads(content)
        except Exception:
            # Fallback to Python literal (e.g., dict) format
            try:
                data = ast.literal_eval(content)
            except Exception:
                # Simple key=value parser as last resort
                data = {} 

def hwc_mixed_004_06(self):
    """ Get the state of a job. If the job is complete this does nothing;
        otherwise it gets a refreshed copy of the job resource.
    """
    # TODO(gram): should we put a choke on refreshes? E.g. if the last call was less than
    # a second ago should we return the cached value?
    if self._is_complete:
      return

    try:
      response = self._api.jobs_get(self._job_id)
    except Exception as e:
      raise e

    if 'status' in response:
      status = response['status']
      if 'state' in status and status['state'] == 'DONE':
        self._end_time = datetime.datetime.utcnow()
        self._is_complete = True
        self._process_job_status(status)

    if 'statistics' in response:
      statistics = response['statistics']
      start_time = statistics.get('creationTime', None)
      end_time = statistics.get('endTime', None)
      if start_time and end_time and end_time >= start_time:
        self._start_time = datetime.datetime.fromtimestamp(float(start_time) / 1000.0)
        self._end_time = datetime.datetime.fromtimestamp(float(end_time) / 1000.0)
