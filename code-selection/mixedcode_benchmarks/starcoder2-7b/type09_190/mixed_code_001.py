def hwc_mixed_001_01(type: ContractParameterType, item: StackItem):
        """
        Convert a StackItem to a ContractParameter object of a specified ContractParameterType
        Args:
            type (neo.SmartContract.ContractParameterType): The ContractParameterType to convert to
            item (neo.VM.InteropService.StackItem): The item to convert to a ContractParameter object

        Returns:

        """
        if type == ContractParameterType.Integer:
            return ContractParameter(type, value=item.GetBigInteger())
        elif type == ContractParameterType.Boolean:
            return ContractParameter(type, value=item.GetBoolean())
        elif type == ContractParameterType.Array:
            output = [ContractParameter.ToParameter(subitem) for subitem in item.GetArray()]
            return ContractParameter(type, value=output)
        elif type == ContractParameterType.String:
            return ContractParameter(type, value=item.GetString())
        elif type == ContractParameterType.InteropInterface:
            return ContractParameter(type, value=item.GetInterface())
        # all other types return a byte array
        else:
            return ContractParameter(type, value=item.GetByteArray()) 

def agc_mixed_001_02(self, entry = None, group = None):
        """Move an entry to another group.

        A v1Group group and a v1Entry entry are needed.

        """

        if entry is None:
            entry = self.entry
        if group is None:
            group = self.group
        if not isinstance(entry, v1Entry):
            raise TypeError("entry must be a v1Entry")
        if not isinstance(group, v1Group):
            raise TypeError("group must be a v1Group")
        if entry.group!= self.group:
            raise ValueError("entry must be in the same group")
        if group.group_id == entry.group.group_id:
            raise ValueError("entry must be in a different group")
        self.api.move_entry(entry.entry_id, group.group_id)
        entry.group = group 

def hwc_mixed_001_03(search, index):
    """Default sort query factory.

    :param query: Search query.
    :param index: Index to search in.
    :returns: Tuple of (query, URL arguments).
    """
    sort_arg_name = 'sort'
    urlfield = request.values.get(sort_arg_name, '', type=str)

    # Get default sorting if sort is not specified.
    if not urlfield:
        # cast to six.text_type to handle unicodes in Python 2
        has_query = request.values.get('q', type=six.text_type)
        urlfield = current_app.config['RECORDS_REST_DEFAULT_SORT'].get(
            index, {}).get('query' if has_query else 'noquery', '')

    # Parse sort argument
    key, asc = parse_sort_field(urlfield)

    # Get sort options
    sort_options = current_app.config['RECORDS_REST_SORT_OPTIONS'].get(
        index, {}).get(key)
    if sort_options is None:
        return (search, {})

    # Get fields to sort query by
    search = search.sort(
        *[eval_field(f, asc) for f in sort_options['fields']]
    )
    return (search, {sort_arg_name: urlfield}) 

def agc_mixed_001_04(api_data, result_info_key, identifier_keys):
    """Generates an Excel workbook object given api_data returned by the Analytics API

    Args:
        api_data: Analytics API data as a list of dicts (one per identifier)
        result_info_key: the key in api_data dicts that contains the data results
        identifier_keys: the list of keys used as requested identifiers
                         (address, zipcode, block_id, etc)

    Returns:
        raw excel file data
    """

    workbook = xlsxwriter.Workbook(result_info_key + '.xlsx')
    worksheet = workbook.add_worksheet()

    # Start from the first cell. Rows and columns are zero indexed.
    row = 0
    col = 0

    # Iterate over the data and write it out row by row.
    for identifier_key in identifier_keys:
        worksheet.write(row, col, identifier_key)
        col += 1
    row += 1

    for api_datum in api_data:
        for identifier_key in identifier_keys:
            worksheet.write(row, col, api_datum[identifier_key])
            col += 1
        row += 1
        col = 0

    workbook.close()

    # Read the file back in
    with open(result_info_key + '.xlsx', 'rb') as f:
        return f.read() 

def agc_mixed_001_05(fname, properties=(u'W', u'F',)):
        """Parse unicode east-asian width tables."""
        with open(fname, 'r') as f:
            lines = f.readlines()
        lines = [l.strip() for l in lines]
        lines = [l for l in lines if l and not l.startswith('#')]
        lines = [l.split('#')[0].strip() for l in lines]
        lines = [l.split() for l in lines]
        lines = [l for l in lines if len(l) == 3]
        lines = [l for l in lines if l[0].isdigit()]
        lines = [l for l in lines if l[1] in properties]
        lines = [l for l in lines if l[2].isdigit()]
        lines = [(int(l[0]), l[1], int(l[2])) for l in lines]
        return lines 

def hwc_mixed_001_06(self, uri, http_method='GET', body=None,
                              headers=None, credentials=None):
        """Extract grant_type and route to the designated handler."""
        django_request = headers.pop("Django-request-object", None)
        request = Request(
            uri, http_method=http_method, body=body, headers=headers)
        request.scopes = None
        request.extra_credentials = credentials
        request.django_request = django_request
        grant_type_handler = self.grant_types.get(request.grant_type,
                                                  self.default_grant_type_handler)
        log.debug('Dispatching grant_type %s request to %r.',
                  request.grant_type, grant_type_handler)
        return grant_type_handler.create_token_response(
            request, self.default_token_type)
