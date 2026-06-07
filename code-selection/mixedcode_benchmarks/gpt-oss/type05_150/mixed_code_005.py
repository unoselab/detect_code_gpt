def hwc_mixed_005_01(self, username, course_id):
        """
        Returns an Certificate object with the user certificates

        Args:
            username (str): an edx user's username
            course_id (str): an edX course id.

        Returns:
            Certificate: object representing the student certificate for a course
        """
        # the request is done in behalf of the current logged in user
        resp = self.requester.get(
            urljoin(
                self.base_url,
                '/api/certificates/v0/certificates/{username}/courses/{course_key}/'.format(
                    username=username,
                    course_key=course_id
                )
            )
        )

        resp.raise_for_status()

        return Certificate(resp.json()) 

def agc_mixed_005_02(d,nkl,**kwargs):
    """
        d = {'scheme': 'http', 'path': '/index.php', 'params': 'params', 'query': 'username=query', 'fragment': 'frag', 'username': '', 'password': '', 'hostname': 'www.baidu.com', 'port': ''}
        pobj(d)
        nkl = ['scheme', 'username', 'password', 'hostname', 'port', 'path', 'params', 'query', 'fragment']
        pobj(_reorder_via_klist(d,nkl))
    """
    result = {}
    seen = set()
    default = kwargs.get('default', None)
    for key in nkl:
        if key in d:
            result[key] = d[key]
            seen.add(key)
        elif default is not None:
            result[key] = default
            seen.add(key)
    for key, value in d.items():
        if key not in seen:
            result[key] = value
    return result 

def agc_mixed_005_03(self):
        """Synchronous OAuth 2.0 Bearer client"""
        import requests

        session = requests.Session()
        token = getattr(self, "access_token", None)

        if token is None:
            get_token = getattr(self, "get_token", None)
            if callable(get_token):
                token = get_token()
            else:
                raise AttributeError("No access token available for sync client")

        session.headers.update({"Authorization": f"Bearer {token}"})
        return session 

def hwc_mixed_005_04(self, args, kwargs):
        """ Raises an ``UnallowedMethodCallError`` with a useful message.

        :raise: ``UnallowedMethodCallError``
        """

        error_message = (
            "Received unexpected call to '{}' on {!r}.  The supplied arguments "
            "{} do not match any available allowances."
        )

        raise UnallowedMethodCallError(
            error_message.format(
                self._method_name,
                self._target.obj,
                build_argument_repr_string(args, kwargs)
            )
        ) 

def agc_mixed_005_05(self, ref, collector, memo=None):
    """Traverses module graph, starting with ref, collecting values for each ref into the sets
    created by the collector function.

    :param ref an IvyModuleRef to start traversing the ivy dependency graph
    :param collector a function that takes a ref and returns a new set of values to collect for
           that ref, which will also be updated with all the dependencies accumulated values
    :param memo is a dict of ref -> set that memoizes the results of each node in the graph.
           If provided, allows for retaining cache across calls.
    :returns the accumulated set for ref
    """

    if memo is None:
        memo = {}
    if ref in memo:
        return memo[ref]

    # Create a new collection for this ref
    collected = collector(ref)
    memo[ref] = collected

    # Retrieve dependencies; fall back to empty iterable if not present
    deps = getattr(ref, "dependencies", None)
    if callable(deps):
        deps = deps()
    if deps is None:
        deps = []

    for dep in deps:
        dep_vals = self.traverse_dependency_graph(dep, collector, memo)
        collected.update(dep_vals)

    return collected 

def hwc_mixed_005_06(self, *iterables):
        """Update the set, adding elements from all *iterables*."""
        _set = self._set
        values = set(chain(*iterables))
        if (4 * len(values)) > len(_set):
            _list = self._list
            _set.update(values)
            _list.clear()
            _list.update(_set)
        else:
            _add = self.add
            for value in values:
                _add(value)
        return self
