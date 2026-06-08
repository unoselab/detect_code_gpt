def agc_mixed_004_01(a, b, scale=1):
    """Intersection between two segments."""
    x1, y1 = a[0], a[1]
    x2, y2 = a[2], a[3]
    x3, y3 = b[0], b[1]
    x4, y4 = b[2], b[3]
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denominator == 0:
        return None
    u_a = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator
    u_b = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator
    if 0 <= u_a <= 1 and 0 <= u_b <= 1:
        x = x1 + u_a * (x2 - x1)
        y = y1 + u_a * (y2 - y1)
        return (x * scale, y * scale)
    else:
        return None 

def agc_mixed_004_02(self, database, query, properties=None):
        """Executes a management command.
        :param str database: Database against query will be executed.
        :param str query: Query to be executed.
        :param azure.kusto.data.request.ClientRequestProperties properties: Optional additional properties.
        :return: Kusto response data set.
        :rtype: azure.kusto.data._response.KustoResponseDataSet
        """
        if not database:
            raise ValueError("Database cannot be empty")
        if not query:
            raise ValueError("Query cannot be empty")
        if properties and not isinstance(properties, ClientRequestProperties):
            raise ValueError("properties must be of type ClientRequestProperties")
        url = f"{self._cluster_uri}/v1/rest/mgmt"
        data = {
            "db": database,
            "query": query,
        }
        if properties:
            data["properties"] = properties.to_dict()
        response = self._session.post(url, json=data)
        response.raise_for_status()
        return KustoResponseDataSet(response.json()) 

def hwc_mixed_004_03(amount_w: int,
                       entropy_w: Union[int, float],
                       entropy_n: Union[int, float],
                       amount_n: int) -> float:
    """Calculate the entropy of a passphrase with given words and numbers."""
    if not isinstance(amount_w, int):
        raise TypeError('amount_w can only be int')
    if not isinstance(entropy_w, (int, float)):
        raise TypeError('entropy_w can only be int or float')
    if not isinstance(entropy_n, (int, float)):
        raise TypeError('entropy_n can only be int or float')
    if not isinstance(amount_n, int):
        raise TypeError('amount_n can only be int')
    if amount_w < 0:
        raise ValueError('amount_w should be greater than 0')
    if entropy_w < 0:
        raise ValueError('entropy_w should be greater than 0')
    if entropy_n < 0:
        raise ValueError('entropy_n should be greater than 0')
    if amount_n < 0:
        raise ValueError('amount_n should be greater than 0')

    return float(amount_w * entropy_w + amount_n * entropy_n) 

def agc_mixed_004_04(organization, github_url, github_token, clone_dir,
                 verbose, filter, exclude):
    """Checkout repositories from a GitHub organization."""
    if not os.path.exists(clone_dir):
        os.makedirs(clone_dir)
    cmd = f'gh repo list {organization} --json name --jq ".[] |.name"'
    if filter:
        cmd += f' | grep "{filter}"'
    if exclude:
        cmd += f' | grep -v "{exclude}"'
    repos = subprocess.check_output(cmd, shell=True).decode().splitlines()
    for repo in repos:
        repo_dir = os.path.join(clone_dir, repo)
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        cmd = f'gh repo clone {organization}/{repo} {repo_dir}'
        if github_token:
            cmd += f' -t {github_token}'
        if verbose:
            cmd +='--verbose'
        subprocess.run(cmd, shell=True) 

def hwc_mixed_004_05(ins):
    """ Defines a memory space with a default set of bytes/words in hexadecimal
    (starting with a number) or literals (starting with #).
    Numeric values with more than 2 digits represents a WORD (2 bytes) value.
    E.g. '01' => 0, '001' => 1, 0 bytes
    Literal values starts with # (1 byte) or ## (2 bytes)
    E.g. '#label + 1' => (label + 1) & 0xFF
         '##(label + 1)' => (label + 1) & 0xFFFF
    """
    output = []
    output.append('%s:' % ins.quad[1])

    q = eval(ins.quad[2])

    for x in q:
        if x[0] == '#':  # literal?
            size_t = 'W' if x[1] == '#' else 'B'
            output.append('DEF{0} {1}'.format(size_t, x.lstrip('#')))
            continue

        # must be an hex number
        x = x.upper()
        assert RE_HEXA.match(x), 'expected an hex number, got "%s"' % x
        size_t = 'B' if len(x) <= 2 else 'W'
        if x[0] > '9':  # Not a number?
            x = '0' + x
        output.append('DEF{0} {1}h'.format(size_t, x))

    return output 

def hwc_mixed_004_06(self, channel, value, unit='A'):
        """Setting current of current source
        """
        dac_offset = self._ch_cal[channel]['DAC']['offset']
        dac_gain = self._ch_cal[channel]['DAC']['gain']
        if unit == 'raw':
            value = value
        elif unit == 'A':
            value = int((-value * 1000000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'mA':
            value = int((-value * 1000 - dac_offset) / dac_gain)  # fix sign of output
        elif unit == 'uA':
            value = int((-value - dac_offset) / dac_gain)  # fix sign of output
        else:
            raise TypeError("Invalid unit type.")

        self._set_dac_value(channel=channel, value=value)
