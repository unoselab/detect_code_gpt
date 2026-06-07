def agc_mixed_005_01(token):
    """
    Unpack a compact-form serialized JWT.
    Returns (header, payload, signature, signing_input) on success
    Raises DecodeError on bad input
    """
    try:
        header, payload, signature = token.split('.')
    except ValueError:
        raise DecodeError('Not enough segments')

    try:
        header_json = base64url_decode(header.encode('utf-8'))
        header = json.loads(header_json)
    except (TypeError, ValueError):
        raise DecodeError('Invalid header string')

    if 'alg' not in header:
        raise DecodeError('Header missing algorithm')

    signing_input = b'.'.join([header_json, payload])

    return header, payload, signature, signing_input 

def agc_mixed_005_02(self):
        """Get the roles associated with the hosts.

        Returns
            dict of role -> [host]
        """

        roles = {}
        for host in self.hosts:
            for role in host.roles:
                if role not in roles:
                    roles[role] = []
                roles[role].append(host)
        return roles 

def agc_mixed_005_03(values, target):
    """
    Return the first index for which target is greater or equal to the first
    item of the tuple found in values
    """
    if not values:
        return 0
    low = 0
    high = len(values) - 1
    while low <= high:
        mid = (low + high) // 2
        if values[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return low 

def hwc_mixed_005_04(self, has_no_column, sum_existing_columns):
        """
        Calculate the average of all columns and return a rounded down number.
        Store the remainder and add it to the last row. Could be implemented
        better. If the enduser wants more control, he can also just add the
        amount of columns. Will work fine with small number (<4) of items in a
        row.

        :param has_no_column:
        :param sum_existing_columns:
        :return: average, columns_for_last_element
        """
        sum_no_columns = len(has_no_column)
        columns_left = self.ALLOWED_COLUMNS - sum_existing_columns

        if sum_no_columns == 0:
            columns_avg = columns_left
        else:
            columns_avg = int(columns_left / sum_no_columns)

        remainder = columns_left - (columns_avg * sum_no_columns)
        columns_for_last_element = columns_avg + remainder
        return columns_avg, columns_for_last_element 

def hwc_mixed_005_05(content=None, dir=None, prefix="tmp", suffix="tmp"):
    """Create temporary file with the given content.

    Please note: the temporary file must be deleted by the caller.

    :param string content: the content to write to the temporary file.
    :param string dir: directory where the file should be created
    :param string prefix: file name prefix
    :param string suffix: file name suffix
    :returns: a string with the path to the temporary file
    """
    if dir is not None:
        if not os.path.exists(dir):
            os.makedirs(dir)
    fh, path = tempfile.mkstemp(dir=dir, prefix=prefix, suffix=suffix)
    _tmp_paths.append(path)
    if content:
        fh = os.fdopen(fh, "wb")
        if hasattr(content, 'encode'):
            content = content.encode('utf8')
        fh.write(content)
        fh.close()
    return path 

def hwc_mixed_005_06(self, prob_dict):
        """ computes the relative probabilities for every state """
        for transition_counts in prob_dict.values():
            summed_occurences = sum(transition_counts.values())
            if summed_occurences > 0:
                for token in transition_counts.keys():
                    transition_counts[token] = transition_counts[
                        token] * 1.0 / summed_occurences
