def hwc_mixed_002_01(orig_units, conv_data, to_units=None, unit_system=None):
    """Convert between E&M & MKS base units.

    If orig_units is a CGS (or MKS) E&M unit, conv_data contains the
    corresponding MKS (or CGS) unit and scale factor converting between them.
    This must be done by replacing the expression of the original unit
    with the new one in the unit expression and multiplying by the scale
    factor.
    """
    conv_unit, canonical_unit, scale = conv_data
    if conv_unit is None:
        conv_unit = canonical_unit
    new_expr = scale * canonical_unit.expr
    if unit_system is not None:
        # we don't know the to_units, so we get it directly from the
        # conv_data
        to_units = Unit(conv_unit.expr, registry=orig_units.registry)
    new_units = Unit(new_expr, registry=orig_units.registry)
    conv = new_units.get_conversion_factor(to_units)
    return to_units, conv 

def agc_mixed_002_02(
        self,
        api_resource,
        auth_token_ticket,
        authenticator,
        private_key,
        service_url=None,
        **kwargs
    ):
        """
        Build an auth-token-protected CAS API url.
        """
        if service_url is None:
            service_url = self.get_service_url()

        return authenticator.get_api_url(
            api_resource,
            auth_token_ticket,
            service_url,
            private_key,
            **kwargs
        ) 

def agc_mixed_002_03(cratedb_version: tuple) -> str:
    """ Return a path to a JAVA_HOME suites for the given CrateDB version """
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        return java_home

    java_home = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "java",
        "jdk-{}.{}.{}.{}-linux-x64".format(*cratedb_version),
    )
    if not os.path.exists(java_home):
        raise RuntimeError(
            "Could not find a JAVA_HOME for CrateDB version {}".format(cratedb_version)
        )
    return java_home 

def hwc_mixed_002_04(args):
    """
    Internal helper method for BorgQueen to process assimilation
    """
    (path, drone, data, status) = args
    newdata = drone.assimilate(path)
    if newdata:
        data.append(json.dumps(newdata, cls=MontyEncoder))
    status['count'] += 1
    count = status['count']
    total = status['total']
    logger.info('{}/{} ({:.2f}%) done'.format(count, total,
                                              count / total * 100)) 

def hwc_mixed_002_05(option_type, from_options):
    """Extract options for specified option type from all options

    :param option_type: the object of specified type of options
    :param from_options: all options dictionary
    :return: the dictionary of options for specified type, each option can be filled by value from all options
             dictionary or blank in case the option for specified type is not exist in all options dictionary
    """
    _options = dict()

    for key in option_type.keys:
        key_with_prefix = f'{option_type.prefix}{key}'
        if key not in from_options and key_with_prefix not in from_options:
            _options[key] = ''
        elif key in from_options:
            _options[key] = from_options.get(key)
        else:
            _options[key] = from_options.get(key_with_prefix)

    return _options 

def agc_mixed_002_06(self, other=None):
        """collect the furthest failure from self and other."""
        if other is None:
            return self
        if self.furthest_failure is None:
            return other
        if other.furthest_failure is None:
            return self
        if self.furthest_failure.distance > other.furthest_failure.distance:
            return self
        return other
