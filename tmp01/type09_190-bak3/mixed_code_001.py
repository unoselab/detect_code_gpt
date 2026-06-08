def agc_mixed_001_01(self, ds):
        """
        Check the axis attribute of coordinate variables

        CF §4 The attribute axis may be attached to a coordinate variable and
        given one of the values X, Y, Z or T which stand for a longitude,
        latitude, vertical, or time axis respectively. Alternatively the
        standard_name attribute may be used for direct identification.

        :param netCDF4.Dataset ds: An open netCDF dataset
        :rtype: list
        :return: List of results
        """
        results = []
        for var_name, var in ds.variables.items():
            if 'axis' in var.ncattrs():
                axis = var.getncattr('axis')
                if axis in ['X', 'Y', 'Z', 'T']:
                    results.append((var_name, axis))
            elif'standard_name' in var.ncattrs():
                standard_name = var.getncattr('standard_name')
                if standard_name in ['longitude', 'latitude', 'height', 'time']:
                    results.append((var_name, standard_name))

        return results 

def hwc_mixed_001_02(self, env, target_name='control',
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

def hwc_mixed_001_04(self):
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

def agc_mixed_001_05(self, key):
        """
        Returns a list with keys of this DAWG that are prefixes of the ``key``.
        """
        prefixes = []
        node = self.root
        for char in key:
            if char not in node.children:
                return []
            node = node.children[char]
        queue = [(node, key)]
        while queue:
            node, prefix = queue.pop(0)
            if node.is_word:
                prefixes.append(prefix)
            for char, child in node.children.items():
                queue.append((child, prefix + char))

        return prefixes 

def agc_mixed_001_06(ins):
    """ Defines a memory space with a default set of bytes/words in hexadecimal
    (starting with a number) or literals (starting with #).
    Numeric values with more than 2 digits represents a WORD (2 bytes) value.
    E.g. '01' => 0, '001' => 1, 0 bytes
    Literal values starts with # (1 byte) or ## (2 bytes)
    E.g. '#label + 1' => (label + 1) & 0xFF
         '##(label + 1)' => (label + 1) & 0xFFFF
    """
    if ins.startswith('0x'):
        value = int(ins[2:], 16)
        if len(ins) == 4:
            return value & 0xFF
        elif len(ins) == 6:
            return value & 0xFFFF
        else:
            raise ValueError("Invalid hexadecimal value")
    elif ins.startswith('#'):
        if len(ins) == 2:
            return eval(ins[1:]) & 0xFF
        elif len(ins) == 3:
            return eval(ins[1:]) & 0xFFFF
        else:
            raise ValueError("Invalid literal value")
    else:
        raise ValueError("Invalid input")
