def agc_mixed_001_01(text, default=False, abort=False, prompt_suffix=': ',
            show_default=True, err=False):
    """Prompts for confirmation (yes/no question).

    If the user aborts the input by sending a interrupt signal this
    function will catch it and raise a :exc:`Abort` exception.

    .. versionadded:: 4.0
       Added the `err` parameter.

    :param text: the question to ask.
    :param default: the default for the prompt.
    :param abort: if this is set to `True` a negative answer aborts the
                  exception by raising :exc:`Abort`.
    :param prompt_suffix: a suffix that should be added to the prompt.
    :param show_default: shows or hides the default value in the prompt.
    :param err: if set to true the file defaults to ``stderr`` instead of
                ``stdout``, the same as with echo.
    """
    import sys

    out = sys.stderr if err else sys.stdout
    prompt = text + prompt_suffix
    if show_default:
        prompt += f" [{ 'Y' if default else 'N' }] "

    try:
        out.write(prompt)
        out.flush()
        response = input().strip().lower()
    except (KeyboardInterrupt, EOFError):
        raise Abort()

    if not response:
        result = default
    elif response in ('y', 'yes'):
        result = True
    elif response in ('n', 'no'):
        result = False
    else:
        return confirm(text, default, abort, prompt_suffix, show_default, err)

    if not result and abort:
        raise Abort()

    return result 

def hwc_mixed_001_02(self) -> Connection:
        """Register and return a connection.

        Coroutine.
        """
        assert not self._closed

        yield from self._condition.acquire()

        while True:
            if self.ready:
                connection = self.ready.pop()
                break
            elif len(self.busy) < self.max_connections:
                connection = self._connection_factory()
                break
            else:
                yield from self._condition.wait()

        self.busy.add(connection)
        self._condition.release()

        return connection 

def hwc_mixed_001_03(key, upDown):
    """ Helper method for special keys.

    Source: http://stackoverflow.com/questions/11045814/emulate-media-key-press-on-mac
    """
    assert upDown in ('up', 'down'), "upDown argument must be 'up' or 'down'"

    key_code = special_key_translate_table[key]

    ev = AppKit.NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            Quartz.NSSystemDefined, # type
            (0,0), # location
            0xa00 if upDown == 'down' else 0xb00, # flags
            0, # timestamp
            0, # window
            0, # ctx
            8, # subtype
            (key_code << 16) | ((0xa if upDown == 'down' else 0xb) << 8), # data1
            -1 # data2
        )

    Quartz.CGEventPost(0, ev.CGEvent()) 

def agc_mixed_001_04(self, rowsPerBlock=1024, colsPerBlock=1024):
        """
        Convert this matrix to a BlockMatrix.

        :param rowsPerBlock: Number of rows that make up each block.
                             The blocks forming the final rows are not
                             required to have the given number of rows.
        :param colsPerBlock: Number of columns that make up each block.
                             The blocks forming the final columns are not
                             required to have the given number of columns.

        >>> rows = sc.parallelize([IndexedRow(0, [1, 2, 3]),
        ...                        IndexedRow(6, [4, 5, 6])])
        >>> mat = IndexedRowMatrix(rows).toBlockMatrix()

        >>> # This IndexedRowMatrix will have 7 effective rows, due to
        >>> # the highest row index being 6, and the ensuing
        >>> # BlockMatrix will have 7 rows as well.
        >>> print(mat.numRows())
        7

        >>> print(mat.numCols())
        3
        """
        from pyspark.mllib.matrix import BlockMatrix, MatrixEntry

        entries = self.entries.map(
            lambda row: [
                MatrixEntry(
                    row.index // rowsPerBlock,
                    col_idx // colsPerBlock,
                    val
                )
                for col_idx, val in enumerate(row.values)
            ]
        ).flatMap(lambda x: x)

        return BlockMatrix(entries, self.numRows(), self.numCols(), rowsPerBlock, colsPerBlock) 

def hwc_mixed_001_05(content, variables_mapping=None):
    """ parse lazy data with evaluated variables mapping.
        Notice: variables_mapping should not contain any variable or function.
    """
    # TODO: refactor type check
    if content is None or isinstance(content, (numeric_types, bool, type)):
        return content

    elif isinstance(content, LazyString):
        variables_mapping = utils.ensure_mapping_format(variables_mapping or {})
        return content.to_value(variables_mapping)

    elif isinstance(content, (list, set, tuple)):
        return [
            parse_lazy_data(item, variables_mapping)
            for item in content
        ]

    elif isinstance(content, dict):
        parsed_content = {}
        for key, value in content.items():
            parsed_key = parse_lazy_data(key, variables_mapping)
            parsed_value = parse_lazy_data(value, variables_mapping)
            parsed_content[parsed_key] = parsed_value

        return parsed_content

    return content 

def agc_mixed_001_06(Name,
                  Value,
                  Description=None,
                  Type='String',
                  KeyId=None,
                  Overwrite=False,
                  AllowedPattern=None,
                  region=None,
                  key=None,
                  keyid=None,
                  profile=None):
    """
    Sets a parameter in the SSM parameter store

    .. versionadded:: Neon

    .. code-block:: text

        salt-call boto_ssm.put_parameter test-param test_value Type=SecureString KeyId=alias/aws/ssm Description='test encrypted key'
    """
    import boto3

    # Handle overlapping argument names
    target_region = region or key or profile # This is a simplification; usually handled by session
    target_key_id = KeyId or keyid

    session = boto3.Session(profile_name=profile, region_name=region)
    ssm = session.client('ssm')

    params = {
        'Name': Name,
        'Value': Value,
        'Type': Type,
        'Overwrite': Overwrite
    }

    if Description:
        params['Description'] = Description
    if target_key_id:
        params['KeyId'] = target_key_id
    if AllowedPattern:
        params['AllowedPattern'] = AllowedPattern

    try:
        response = ssm.put_parameter(**params)
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to put SSM parameter {Name}: {str(e)}")
