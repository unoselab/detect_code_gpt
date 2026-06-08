def agc_mixed_001_01(self, path=None, fatal=True, logger=None):
        """
        :param str|None path: Load this object from file with 'path' (default: self._path)
        :param bool|None fatal: Abort execution on failure if True
        :param callable|None logger: Logger to use
        """
        if path is None:
            path = self._path
        if logger is None:
            logger = self._logger
        try:
            with open(path, 'r') as f:
                data = f.read()
                self._data = data
        except Exception as e:
            if fatal:
                raise e
            else:
                logger.error(f'Failed to load data from {path}: {e}') 

def agc_mixed_001_02(self):
        """
        Returns errors on:
        Certificate, PrivateKey or Chain not being properly formatted
        Arn not existing if its provided
        PrivateKey size > 2048
        Certificate expired or is not yet in effect

        Does not return errors on:
        Checking Certificate is legit, or a selfsigned chain is provided

        :return: str(JSON) for response
        """
        errors = []
        if not self.certificate:
            errors.append("Certificate not properly formatted")
        if not self.private_key:
            errors.append("PrivateKey not properly formatted")
        if not self.chain:
            errors.append("Chain not properly formatted")
        if self.arn and not self.certificate_manager.get_certificate(self.arn):
            errors.append("Arn not existing")
        if len(self.private_key) > 2048:
            errors.append("PrivateKey size > 2048")
        if self.certificate.not_valid_before > datetime.now() or self.certificate.not_valid_after < datetime.now():
            errors.append("Certificate expired or is not yet in effect")
        return json.dumps(errors) 

def hwc_mixed_001_03(self):
        """Returns the ARN user or role whose credentials are used to call the API.
        Returns:
            (str): The ARN user or role
        """
        assumed_role = self.boto_session.client('sts').get_caller_identity()['Arn']

        if 'AmazonSageMaker-ExecutionRole' in assumed_role:
            role = re.sub(r'^(.+)sts::(\d+):assumed-role/(.+?)/.*$', r'\1iam::\2:role/service-role/\3', assumed_role)
            return role

        role = re.sub(r'^(.+)sts::(\d+):assumed-role/(.+?)/.*$', r'\1iam::\2:role/\3', assumed_role)

        # Call IAM to get the role's path
        role_name = role[role.rfind('/') + 1:]
        try:
            role = self.boto_session.client('iam').get_role(RoleName=role_name)['Role']['Arn']
        except ClientError:
            LOGGER.warning("Couldn't call 'get_role' to get Role ARN from role name {} to get Role path."
                           .format(role_name))

        return role 

def agc_mixed_001_04(start, end, periods, offset):
    """Generate a regular range of cftime.datetime objects with a
    given time offset.

    Adapted from pandas.tseries.offsets.generate_range.

    Parameters
    ----------
    start : cftime.datetime, or None
        Start of range
    end : cftime.datetime, or None
        End of range
    periods : int, or None
        Number of elements in the sequence
    offset : BaseCFTimeOffset
        An offset class designed for working with cftime.datetime objects

    Returns
    -------
    A generator object
    """
    if periods is not None:
        if start is not None:
            end = start + offset * (periods - 1)
        else:
            start = end - offset * (periods - 1)
    else:
        if start is not None and end is not None:
            periods = int((end - start) / offset) + 1
        else:
            raise ValueError("Either `periods` or both `start` and `end` must be specified")

    if start is not None:
        yield start

    for _ in range(periods - 1):
        start += offset
        yield start 

def hwc_mixed_001_05(self):
        """Raises an exception if there was an error. Otherwise, do nothing.

        Clients should handle these errors, since these require custom handling
        to properly resolve.
        """
        if self.is_success():
            return

        # Handle the error if we have any information
        if self.details:
            error = self.details.get('error', None)

            if error == PushResponse.ERROR_DEVICE_NOT_REGISTERED:
                raise DeviceNotRegisteredError(self)
            elif error == PushResponse.ERROR_MESSAGE_TOO_BIG:
                raise MessageTooBigError(self)
            elif error == PushResponse.ERROR_MESSAGE_RATE_EXCEEDED:
                raise MessageRateExceededError(self)

        # No known error information, so let's raise a generic error.
        raise PushResponseError(self) 

def hwc_mixed_001_06(self, env, target_name='control',
                     file_name='control.json',
                     encoder_cls=SConsEncoder):
        """
        Adds a target to build a control file at each of the current leaves.

        :param env: SCons Environment object
        :param target_name: Name for target in nest
        :param file_name: Name for output file.
        """
        if not HAS_SCONS:
            raise ImportError('SCons not available')

        @self.add_target(name=target_name)
        def control(outdir, c):
            return env.Command(os.path.join(outdir, file_name),
                               [],
                               action=_create_control_file,
                               control_dict=c,
                               encoder_cls=encoder_cls)
