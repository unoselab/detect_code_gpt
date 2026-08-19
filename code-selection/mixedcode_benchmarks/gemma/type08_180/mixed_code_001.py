def agc_mixed_001_01(self):
        """Convert to a nested dict. """
        result = {}
        for key, value in self.__dict__.items():
            if hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [item.to_dict() if hasattr(item, 'to_dict') else item for item in value]
            elif isinstance(value, dict):
                result[key] = {k: (v.to_dict() if hasattr(v, 'to_dict') else v) for k, v in value.items()}
            else:
                result[key] = value
        return result 

def hwc_mixed_001_02(config_file):
    """Load settings from config file and return them as a dict.  If the
    config file is not found, or if it is invalid, create and use a
    default config file.

    :param config_file: `pathlib.Path` object. Path to config file.
    :return: Dictionary of config options.
    """
    logger.debug('Config file: {}'.format(config_file))

    parser = configparser.ConfigParser()
    try:
        with config_file.open('r') as f:
            parser.read_file(f)

    except FileNotFoundError as e:
        logger.warning('Config file not found')
        parser = _use_default(config_file)

    except configparser.ParsingError as e:
        logger.warning('Error in config file: {}'.format(e))
        parser = _use_default(config_file)

    finally:
        try:
            config = _load_options(parser)
        except (configparser.NoOptionError):
            parser = _use_default(config_file)
            config = _load_options(parser)

        logger.debug('Config loaded: {}'.format(config_file))
        return config 

def hwc_mixed_001_03(data):
    """
    Returns the data where the expression is normalized so that the total
    count per cell is equal.
    """
    if sparse.issparse(data):
        data = sparse.csc_matrix(data.astype(float))
        # normalize in-place
        sparse_cell_normalize(data.data,
                data.indices,
                data.indptr,
                data.shape[1],
                data.shape[0])
        return data
    data_norm = data.astype(float)
    total_umis = []
    for i in range(data.shape[1]):
        di = data_norm[:,i]
        total_umis.append(di.sum())
        di /= total_umis[i]
    med = np.median(total_umis)
    data_norm *= med
    return data_norm 

def hwc_mixed_001_04(self, raw_response):
        """
            Put in self.result the data from the response
            Can generate exception if the command and the response id does not match
            of if the response is an error
            :param raw_response:  Not decoded one string response
        """
        # Transform response into a dict
        import json
        data = json.loads(raw_response)
        # Retrieve the response id
        self.response_id = data[self.RESPONSE_ID]
        # Check if the response id match the command id
        self.check_id()
        # Get response data
        if self.RESPONSE_RESULT in data:
            self.result = data[self.RESPONSE_RESULT]
        elif self.RESPONSE_ERROR in data:
            # If the response is an error raise YeelightError Exception
            message = data[self.RESPONSE_ERROR][self.ERROR_MESSAGE]
            code = data[self.RESPONSE_ERROR][self.ERROR_CODE]
            raise YeelightError(message, code, self.command) 

def agc_mixed_001_05(self, tup_tree):
        """
        Parse a VALUE.REFERENCE element and return the instance path or class
        path it represents as a CIMInstanceName or CIMClassName object,
        respectively.

          ::

            <!ELEMENT VALUE.REFERENCE (CLASSPATH | LOCALCLASSPATH | CLASSNAME |
                                       INSTANCEPATH | LOCALINSTANCEPATH |
                                       INSTANCENAME)>
        """

        element = tup_tree[0]
        if element.tag == 'CLASSPATH':
            return self.parse_class_path(element)
        elif element.tag == 'LOCALCLASSPATH':
            return self.parse_local_class_path(element)
        elif element.tag == 'CLASSNAME':
            return self.parse_class_name(element)
        elif element.tag == 'INSTANCEPATH':
            return self.parse_instance_path(element)
        elif element.tag == 'LOCALINSTANCEPATH':
            return self.parse_local_instance_path(element)
        elif element.tag == 'INSTANCENAME':
            return self.parse_instance_name(element)
        else:
            raise ValueError(f"Unexpected element in VALUE.REFERENCE: {element.tag}") 

def agc_mixed_001_06(a, b, c, deriv=0):
    """Similar to opbend_angle, but with relative vectors"""
    import numpy as np
    v1 = a - b
    v2 = c - b
    v1_norm = np.linalg.norm(v1)
    v2_norm = np.linalg.norm(v2)
    cos_theta = np.dot(v1, v2) / (v1_norm * v2_norm)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    angle = np.arccos(cos_theta)
    if deriv == 0:
        return angle

    # Derivative of arccos(u) is -1/sqrt(1-u^2) * du/dx
    # u = (v1 . v2) / (|v1||v2|)
    sin_theta = np.sqrt(1.0 - cos_theta**2)
    if sin_theta < 1e-8:
        return np.zeros_like(angle)

    # This is a simplified derivative placeholder as the specific 
    # variable of differentiation isn't specified in the signature.
    # Typically, this would return the gradient w.r.t a, b, or c.
    return -1.0 / sin_theta
