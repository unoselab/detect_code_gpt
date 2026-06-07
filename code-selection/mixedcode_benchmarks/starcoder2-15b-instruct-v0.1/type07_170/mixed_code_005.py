def hwc_mixed_005_01(self):
        """Return undeclared query parameters from job statistics, if present.

        See:
        https://cloud.google.com/bigquery/docs/reference/rest/v2/jobs#statistics.query.undeclaredQueryParameters

        :rtype:
            list of
            :class:`~google.cloud.bigquery.ArrayQueryParameter`,
            :class:`~google.cloud.bigquery.ScalarQueryParameter`, or
            :class:`~google.cloud.bigquery.StructQueryParameter`
        :returns: undeclared parameters, or an empty list if the query has
                  not yet completed.
        """
        parameters = []
        undeclared = self._job_statistics().get("undeclaredQueryParameters", ())

        for parameter in undeclared:
            p_type = parameter["parameterType"]

            if "arrayType" in p_type:
                klass = ArrayQueryParameter
            elif "structTypes" in p_type:
                klass = StructQueryParameter
            else:
                klass = ScalarQueryParameter

            parameters.append(klass.from_api_repr(parameter))

        return parameters 

def agc_mixed_005_02(self, container, msg=None):
        """Fail if elements in ``container`` are not unique.

        Parameters
        ----------
        container : iterable
        msg : str
            If not provided, the :mod:`marbles.mixins` or
            :mod:`unittest` standard message will be used.

        Raises
        ------
        TypeError
            If ``container`` is not iterable.
        """
        try:
            iterator = iter(container)
        except TypeError:
            raise TypeError("The container must be iterable.")
        seen = set()
        for element in iterator:
            if element in seen:
                if msg is None:
                    msg = f"Elements in the container are not unique: {element} is duplicated."
                raise AssertionError(msg)
            seen.add(element) 

def hwc_mixed_005_03(self, mean, std, pred_init=None, deg_gauss_hermite=20):
        """
        Calculate the warped variance by using Gauss-Hermite quadrature.
        """
        gh_samples, gh_weights = np.polynomial.hermite.hermgauss(deg_gauss_hermite)
        gh_samples = gh_samples[:, None]
        gh_weights = gh_weights[None, :]
        arg1 = gh_weights.dot(self._get_warped_term(mean, std, gh_samples, 
                                                    pred_init=pred_init) ** 2) / np.sqrt(np.pi)
        arg2 = self._get_warped_mean(mean, std, pred_init=pred_init,
                                     deg_gauss_hermite=deg_gauss_hermite)
        return arg1 - (arg2 ** 2) 

def hwc_mixed_005_04(self, task_name, param_name):
        """
        Yield the parameter values, with optional deprecation warning as second tuple value.

        The parameter value will be whatever non-_no_value that is yielded first.
        """
        cp_parser = CmdlineParser.get_instance()
        if cp_parser:
            dest = self._parser_global_dest(param_name, task_name)
            found = getattr(cp_parser.known_args, dest, None)
            yield (self._parse_or_no_value(found), None)
        yield (self._get_value_from_config(task_name, param_name), None)
        if self._config_path:
            yield (self._get_value_from_config(self._config_path['section'], self._config_path['name']),
                   'The use of the configuration [{}] {} is deprecated. Please use [{}] {}'.format(
                       self._config_path['section'], self._config_path['name'], task_name, param_name))
        yield (self._default, None) 

def agc_mixed_005_05(self, leagueid=None, **kwargs):
        """Returns a dictionary that includes community funded tournament prize pools

        :param leagueid: (int, optional)
        :return: dictionary of prize pools, see :doc:`responses </responses>`
        """
        if leagueid is not None:
            return self._request(
                "GET",
                f"tournament/prize_pool?leagueid={leagueid}",
                **kwargs
            )
        else:
            return self._request(
                "GET",
                "tournament/prize_pool",
                **kwargs
            ) 

async def agc_mixed_005_06(request):
    """
    This initializes a call to pipette.home() which, as a side effect will:
        1. Check the pipette is actually connected (will throw an error if you
        try to home a non-connected pipette)
        2. Re-engages the motor
    :param request: Information obtained from a POST request.
        The content type is application/json.
        The correct packet form should be as follows:
        {
        'target': Can be, 'robot' or 'pipette'
        'mount': 'left' or 'right', only used if target is pipette
        }
    :return: A success or non-success message.
    """
    data = request.json()
    target = data['target']
    mount = data['mount']
    if target == 'robot':
        await robot.home()
        return 'Robot homed successfully'
    elif target == 'pipette':
        if mount == 'left':
            await left_pipette.home()
            return 'Left pipette homed successfully'
        elif mount == 'right':
            await right_pipette.home()
            return 'Right pipette homed successfully'
        else:
            return 'Invalid mount'
    else:
        return 'Invalid target'
