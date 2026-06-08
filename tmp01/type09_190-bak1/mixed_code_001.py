def hwc_mixed_001_01(self, collection, query):
        """
        :param str collection: The name of the collection for the request.
        :param dict query: Dictionary of solr args.

        Will page through the result set in increments using cursorMark until it has all items. Sort is required for cursorMark \
        queries, if you don't specify it, the default is 'id desc'.

        Returns an iterator of SolrResponse objects. For Example::

            >>> for res in solr.cursor_query('SolrClient_unittest',{'q':'*:*'}):
                    print(res)
        """
        cursor = '*'
        if 'sort' not in query:
            query['sort'] = 'id desc'
        while True:
            query['cursorMark'] = cursor
            # Get data with starting cursorMark
            results = self.query(collection, query)
            if results.get_results_count():
                cursor = results.get_cursor()
                yield results
            else:
                self.logger.debug("Got zero Results with cursor: {}".format(cursor))
                break 

def hwc_mixed_001_02():
    """
    Read all the template's files
    """

    files_root = path.join(path.dirname(__file__), 'files')

    for root, dirs, files in walk(files_root):
        rel_root = path.relpath(root, files_root)

        for file_name in files:
            try:
                f = open(path.join(root, file_name), 'r', encoding='utf-8')
                with f:
                    yield rel_root, file_name, f.read(), True
            except UnicodeError:
                f = open(path.join(root, file_name), 'rb')
                with f:
                    yield rel_root, file_name, f.read(), False 

def agc_mixed_001_03(shape, inds=None, return_directions=True):
    """
    Get list of grid edges
    :param shape:
    :param inds:
    :param return_directions:
    :return:
    """
    if inds is None:
        inds = np.arange(np.prod(shape)).reshape(shape)
    edges = []
    directions = []
    for i in range(shape[0]):
        for j in range(shape[1]):
            if i < shape[0] - 1:
                edges.append([inds[i, j], inds[i + 1, j]])
                directions.append([0, 1])
            if j < shape[1] - 1:
                edges.append([inds[i, j], inds[i, j + 1]])
                directions.append([1, 0])
    if return_directions:
        return edges, directions
    else:
        return edges 

def agc_mixed_001_04(self):
        """
        Get past PythonKC meetup events.

        Returns
        -------
        List of ``pythonkc_meetups.types.MeetupEvent``, ordered by event time,
        descending.

        Exceptions
        ----------
        * PythonKCMeetupsBadJson
        * PythonKCMeetupsBadResponse
        * PythonKCMeetupsMeetupDown
        * PythonKCMeetupsNotJson
        * PythonKCMeetupsRateLimitExceeded

        """

        response = self.client.get_events()
        if response.status_code!= 200:
            raise PythonKCMeetupsBadResponse(response.status_code)
        try:
            json_response = response.json()
        except ValueError:
            raise PythonKCMeetupsNotJson(response.text)
        if 'errors' in json_response:
            raise PythonKCMeetupsBadJson(json_response['errors'])
        if 'rate_limit_exceeded' in json_response:
            raise PythonKCMeetupsRateLimitExceeded(json_response['rate_limit_exceeded'])
        if 'problem' in json_response:
            raise PythonKCMeetupsMeetupDown(json_response['problem'])
        events = [MeetupEvent(event) for event in json_response]
        events.sort(key=lambda event: event.time, reverse=True)

        return events 

def hwc_mixed_001_05(self):
        """
        Chooses next available server to connect.
        """
        if self.options["dont_randomize"]:
            server = self._server_pool.pop(0)
            self._server_pool.append(server)
        else:
            shuffle(self._server_pool)

        s = None
        for server in self._server_pool:
            if self.options["max_reconnect_attempts"] > 0 and (
                    server.reconnects >
                    self.options["max_reconnect_attempts"]):
                continue
            else:
                s = server
        return s 

def agc_mixed_001_06(organization, github_url, github_token, clone_dir,
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
