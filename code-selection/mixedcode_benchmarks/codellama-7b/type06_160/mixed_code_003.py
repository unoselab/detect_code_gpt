def agc_mixed_003_01(item, vendored_libs):
    """Rewrite 'import xxx' and 'from xxx import' for vendored_libs"""
    if item.startswith('import '):
        for lib in vendored_libs:
            if item.startswith('import ' + lib):
                item = 'import ' + vendored_libs[lib]
                break
    elif item.startswith('from '):
        for lib in vendored_libs:
            if item.startswith('from ' + lib + ' import'):
                item = 'from ' + vendored_libs[lib] + ' import'
                break
    return item 

def agc_mixed_003_02(self, value, store_type):
        """Save the key value base on it's storage type."""
        if store_type == 'string':
            self.encode_key_value = value
        elif store_type == 'bytes':
            self.encode_key_value = bytes(value, 'utf-8')
        elif store_type == 'int':
            self.encode_key_value = int(value)
        elif store_type == 'float':
            self.encode_key_value = float(value)
        elif store_type == 'bool':
            self.encode_key_value = bool(value)
        else:
            raise ValueError('Unknown store type: {}'.format(store_type)) 

def agc_mixed_003_03(recfile):
    """read the phi components from a record file by iteration

    Parameters
    ----------
    recfile : str
        pest record file name

    Returns
    -------
    iters : dict
        nested dictionary of iteration number, {group,contribution}

    """
    iters = {}
    with open(recfile, 'r') as f:
        for line in f:
            if line.startswith('ITER'):
                iters[int(line.split()[1])] = {}
            elif line.startswith('GROUP'):
                iters[int(line.split()[1])][line.split()[2]] = {}
            elif line.startswith('CONTRIBUTION'):
                iters[int(line.split()[1])][line.split()[2]][line.split()[3]] = {}
            elif line.startswith('PARAMETER'):
                iters[int(line.split()[1])][line.split()[2]][line.split()[3]][line.split()[4]] = float(line.split()[5])

    return iters 

def hwc_mixed_003_04(addr):
    """
    parse host address to get domain name or ipv4/v6 address,
    cidr prefix and net mask code string if given a subnet address

    :param addr:
    :type addr: str
    :return: parsed domain name/ipv4 address/ipv6 address,
             cidr prefix if there is,
             net mask code string if there is
    :rtype: (string, int, string)
    """

    if addr.startswith('[') and addr.endswith(']'):
        addr = addr[1:-1]

    parts = addr.split('/')
    if len(parts) == 1:
        return parts[0], None, None
    if len(parts) > 2:
        raise ValueError("Illegal host address")
    else:
        domain_or_ip, prefix = parts
        prefix = int(prefix)
        if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", domain_or_ip):
            return domain_or_ip, prefix, ipv4_prefix_to_mask(prefix)
        elif ':' in domain_or_ip:
            return domain_or_ip, prefix, ipv6_prefix_to_mask(prefix)
        else:
            return domain_or_ip, None, None 

def hwc_mixed_003_05(self, oprnd1, oprnd2, oprnd3):
        """Return a formula representation of an ADD instruction.
        """
        assert oprnd1.size and oprnd2.size and oprnd3.size
        assert oprnd1.size == oprnd2.size

        op1_var = self._translate_src_oprnd(oprnd1)
        op2_var = self._translate_src_oprnd(oprnd2)
        op3_var, op3_var_constrs = self._translate_dst_oprnd(oprnd3)

        if oprnd3.size > oprnd1.size:
            result = smtfunction.zero_extend(op1_var, oprnd3.size) + smtfunction.zero_extend(op2_var, oprnd3.size)
        elif oprnd3.size < oprnd1.size:
            result = smtfunction.extract(op1_var + op2_var, 0, oprnd3.size)
        else:
            result = op1_var + op2_var

        return [op3_var == result] + op3_var_constrs 

def hwc_mixed_003_06(self, password):
        """Attempts to log in as the current user with given password"""

        if self.logged_in:
            raise RuntimeError("User already logged in!")

        params = {"name": self.nick, "password": password}
        resp = self.conn.make_api_call("login", params)
        if "error" in resp:
            raise RuntimeError(
                f"Login failed: {resp['error'].get('message') or resp['error']}"
            )
        self.session = resp["session"]
        self.conn.make_call("useSession", self.session)
        self.conn.cookies.update({"session": self.session})
        self.logged_in = True
        return True
