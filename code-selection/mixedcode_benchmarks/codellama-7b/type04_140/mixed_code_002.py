def hwc_mixed_002_01(instance, encoding='utf-8'):
    """Convert an instance recursively to string."""
    if isinstance(instance, str):
        return instance
    elif hasattr(instance, 'decode'):
        return instance.decode(encoding)
    elif isinstance(instance, list):
        return list([to_str(item, encoding) for item in instance])
    elif isinstance(instance, tuple):
        return tuple([to_str(item, encoding) for item in instance])
    elif isinstance(instance, dict):
        return dict(
            [(to_str(key, encoding), to_str(value, encoding))
                for key, value in instance.items()])
    else:
        return instance 

def agc_mixed_002_02(self, url, method, data=None, **kwargs):
        """url -> full target url
           method -> method from requests
           data -> request body
           kwargs -> url formatting args
        """
        url = self.base_url + url.format(**kwargs)
        if method == 'GET':
            return self.session.get(url, **kwargs)
        elif method == 'POST':
            return self.session.post(url, data=data, **kwargs)
        elif method == 'PUT':
            return self.session.put(url, data=data, **kwargs)
        elif method == 'DELETE':
            return self.session.delete(url, **kwargs)
        else:
            raise ValueError('Invalid method: {}'.format(method)) 

def hwc_mixed_002_03(lhs, rhs):
    """Simplification method for lhs << rhs

    Decompose a series product of two reducible circuits with compatible block
    structures into a concatenation of individual series products between
    subblocks.  This method raises CannotSimplify when rhs is a CPermutation in
    order not to conflict with other _rules.
    """
    if isinstance(rhs, CPermutation):
        raise CannotSimplify()
    lhs_structure = lhs.block_structure
    rhs_structure = rhs.block_structure
    res_struct = _get_common_block_structure(lhs_structure, rhs_structure)
    if len(res_struct) > 1:
        blocks, oblocks = (
            lhs.get_blocks(res_struct),
            rhs.get_blocks(res_struct))
        parallel_series = [SeriesProduct.create(lb, rb)
                           for (lb, rb) in zip(blocks, oblocks)]
        return Concatenation.create(*parallel_series)
    raise CannotSimplify() 

def agc_mixed_002_04(self, values, unit=None, raise_exception=True):
        """Check if a list of values is within physically/mathematically possible range.

        Args:
            values: A list of values.
            unit: The unit of the values.  If not specified, the default metric
                unit will be assumed.
            raise_exception: Set to True to raise an exception if not in range.
        """
        if unit is None:
            unit = self.default_unit
        if not isinstance(values, list):
            values = [values]
        if not all(self.is_in_range_single(value, unit=unit) for value in values):
            if raise_exception:
                raise ValueError("Value(s) out of range")
            else:
                return False
        return True 

def agc_mixed_002_05(self, name, parents=None):
        """
        add a node to the graph.

        Raises an exception if the node cannot be added (i.e., if a node
        that name already exists, or if it would create a cycle.

        NOTE: A node can be added before its parents are added.

        name: The name of the node to add to the graph. Name can be any
            unique Hashable value.
        parents: (optional, None) The name of the nodes parents.
        """
        if name in self.nodes:
            raise ValueError("Node %s already exists" % name)

        if parents is None:
            parents = []

        if not isinstance(parents, list):
            parents = [parents]

        for parent in parents:
            if parent not in self.nodes:
                raise ValueError("Parent %s does not exist" % parent)

        self.nodes[name] = parents 

def hwc_mixed_002_06(self, env_with_dig='ingi/inginious-c-default'):
        """
        Get the external IP of the host of the docker daemon. Uses OpenDNS internally.
        :param env_with_dig: any container image that has dig
        """
        try:
            container = self._docker.containers.create(env_with_dig, command="dig +short myip.opendns.com @resolver1.opendns.com")
            container.start()
            response = container.wait()
            assert response["StatusCode"] == 0 if isinstance(response, dict) else response == 0
            answer = container.logs(stdout=True, stderr=False).decode('utf8').strip()
            container.remove(v=True, link=False, force=True)
            return answer
        except:
            return None
