def agc_mixed_002_01(resource, port=50342, msi_conf=None):
    """Get MSI token if MSI_ENDPOINT is set.

    IF MSI_ENDPOINT is not set, will try legacy access through 'http://localhost:{}/oauth2/token'.format(port).

    If msi_conf is used, must be a dict of one key in ["client_id", "object_id", "msi_res_id"]

    :param str resource: The resource where the token would be use.
    :param int port: The port if not the default 50342 is used. Ignored if MSI_ENDPOINT is set.
    :param dict[str,str] msi_conf: msi_conf if to request a token through a User Assigned Identity (if not specified, assume System Assigned)
    """
    msi_endpoint = os.environ.get('MSI_ENDPOINT')
    if msi_endpoint:
        msi_token_url = '{}?resource={}&api-version=2017-09-01'.format(msi_endpoint, resource)
        if msi_conf:
            msi_token_url += '&{}'.format(msi_conf)
        msi_token_response = urllib.request.urlopen(msi_token_url)
        msi_token = msi_token_response.read().decode('utf-8')
        return json.loads(msi_token)['access_token']
    else:
        legacy_token_url = 'http://localhost:{}/oauth2/token'.format(port)
        legacy_token_response = urllib.request.urlopen(legacy_token_url, data=b'resource={}'.format(resource).encode('utf-8'))
        legacy_token = legacy_token_response.read().decode('utf-8')
        return json.loads(legacy_token)['access_token'] 

def agc_mixed_002_02(cls, diff_dict):
        """
        Returns a list of string message with the differences in a diff dict.

        Each inner difference is tabulated two space deeper
        """
        changes = []
        for key, value in diff_dict.items():
            if isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    changes.append(f"\t{key}.{inner_key}: {inner_value}")
            else:
                changes.append(f"\t{key}: {value}")
        return changes 

def hwc_mixed_002_03(_bytearray, byte_index, bool_index, value):
    """
    Set boolean value on location in bytearray
    """
    assert value in [0, 1, True, False]
    current_value = get_bool(_bytearray, byte_index, bool_index)
    index_value = 1 << bool_index

    # check if bool already has correct value
    if current_value == value:
        return

    if value:
        # make sure index_v is IN current byte
        _bytearray[byte_index] += index_value
    else:
        # make sure index_v is NOT in current byte
        _bytearray[byte_index] -= index_value 

def hwc_mixed_002_04(self, x, type='conv', epsilon=1e-3):
        """
        Batch Normalization: Apply mean subtraction and variance scaling
        :param x: input feature map stack
        :param type: string, either 'conv' or 'fc'
        :param epsilon: float
        :return: output feature map stack
        """
        # Determine indices over which to calculate moments, based on layer type
        if type == 'conv':
            size = [0, 1, 2]
        else:  # type == 'fc'
            size = [0]

        # Calculate batch mean and variance
        batch_mean1, batch_var1 = tf.nn.moments(x, size, keep_dims=True)

        # Apply the initial batch normalizing transform
        z1_hat = (x - batch_mean1) / tf.sqrt(batch_var1 + epsilon)
        return z1_hat 

def agc_mixed_002_05(dict_of_seqs, stats_key=None, sep=','):
    """Join (stringify and concatenate) keys (table fields) in a dict (table) of sequences (columns)

    >>> consolidate_stats(dict([('c', [1, 1, 1]), ('cm', ['P', 6, 'Q']), ('cn', [0, 'MUS', 'ROM']),
    ...                        ('ct', [0, 2, 0])]), stats_key='c')
    [{'P,0,0': 1}, {'6,MUS,2': 1}, {'Q,ROM,0': 1}]
    >>> consolidate_stats([{'c': 1, 'cm': 'P', 'cn': 0, 'ct': 0}, {'c': 1, 'cm': 6, 'cn': 'MUS', 'ct': 2},
    ...                    {'c': 1, 'cm': 'Q', 'cn': 'ROM', 'ct': 0}], stats_key='c')
    [{'P,0,0': 1}, {'6,MUS,2': 1}, {'Q,ROM,0': 1}]
    """
    if isinstance(dict_of_seqs, dict):
        dict_of_seqs = [dict_of_seqs]
    stats = {}
    for d in dict_of_seqs:
        key = stats_key
        value = d[stats_key]
        for k, v in d.items():
            if k!= stats_key:
                key += f'{sep}{v}'
        stats[key] = stats.get(key, 0) + 1
    return [stats] 

def hwc_mixed_002_06(self, process):
        """
        Reads the stdout of `process` and forwards lines and progress
        to any interested subscribers
        """
        while True:
            line = process.stdout.readline()
            if not line:
                break
            pub.send_message(events.CONSOLE_UPDATE, msg=line.decode(self.encoding))
            pub.send_message(events.PROGRESS_UPDATE,
                             progress=self._extract_progress(line))
        pub.send_message(events.EXECUTION_COMPLETE)
