def hwc_mixed_001_01(id_list: Iterable[str]) -> Dict[str, List[str]]:
    """
    Given a list of ids return their types

    :param id_list: list of ids
    :return: dictionary where the id is the key and the value is a list of types
    """
    type_map = {}
    filter_out_types = [
        'cliqueLeader',
        'Class',
        'Node',
        'Individual',
        'quality',
        'sequence feature'
    ]

    for node in get_scigraph_nodes(id_list):
        type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                if typ not in filter_out_types]

    return type_map 

def agc_mixed_001_02(self, shortlink_id_or_url):
        """Retrieve registered shortlink info

        Arguments:
            shortlink_id_or_url:
                Shortlink id or url, assigned by mCASH
        """
        if not isinstance(shortlink_id_or_url, str):
            raise ValueError("shortlink_id_or_url must be a string")

        if not shortlink_id_or_url.startswith("http"):
            shortlink_id_or_url = "http://%s" % shortlink_id_or_url

        url = "%s/shortlink/%s" % (self.base_url, shortlink_id_or_url)
        response = self.session.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(response.text) 

def hwc_mixed_001_03(input_value):
        """Recursively serialize task input list"""
        input_list = []
        for item in input_value:
            if isinstance(item, list):
                input_list.append(Task._serialize_input_list(item))
            else:
                if isinstance(item, File):
                    item = Task._to_api_file_format(item)
                input_list.append(item)
        return input_list 

def hwc_mixed_001_04(node, context=None):
    """Infer length calls

    :param nodes.Call node: len call to infer
    :param context.InferenceContext: node context
    :rtype nodes.Const: a Const node with the inferred length, if possible
    """
    call = arguments.CallSite.from_call(node)
    if call.keyword_arguments:
        raise UseInferenceDefault("TypeError: len() must take no keyword arguments")
    if len(call.positional_arguments) != 1:
        raise UseInferenceDefault(
            "TypeError: len() must take exactly one argument "
            "({len}) given".format(len=len(call.positional_arguments))
        )
    [argument_node] = call.positional_arguments
    try:
        return nodes.Const(helpers.object_len(argument_node, context=context))
    except (AstroidTypeError, InferenceError) as exc:
        raise UseInferenceDefault(str(exc)) from exc 

def agc_mixed_001_05(self, hour):
        """Check what the analemma position is for an hour.

        This is useful for calculating hours of analemma curves.

        Returns:
            -1 if always night,
            0 if both day and night,
            1 if always day.
        """
        # check for 21 dec and 21 jun
        if self.night_start is None:
            return 0
        if self.night_start > self.night_end:
            if hour >= self.night_start or hour < self.night_end:
                return -1
        else:
            if hour >= self.night_start and hour < self.night_end:
                return -1
        return 1 

def agc_mixed_001_06(self):
        """
        Request URL and parse response. Yield a ``Torrent`` for every torrent
        on page.
        """
        for page in itertools.count(1):
            url = self.url.format(page=page)
            response = requests.get(url)
            if response.status_code!= 200:
                raise ValueError('Could not get page {}'.format(page))
            soup = BeautifulSoup(response.text, 'html.parser')
            for torrent in soup.find_all('tr', class_='torrent'):
                yield Torrent(torrent)
