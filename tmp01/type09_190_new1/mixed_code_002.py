def hwc_mixed_002_01(target_type, **kwargs):
        """
        :param target_type: string, either image, dockertar, ostree or dockerfile
        """
        if target_type in TARGET_TYPES:
            cls = TARGET_TYPES[target_type]
            try:
                return cls(**kwargs)
            except Exception:
                logger.error("Please make sure that you picked the correct target type: "
                             "--target-type CLI option.")
                raise

        raise ColinException(
            "Unknown target type '{}'. Please make sure that you picked the correct target type: "
            "--target-type CLI option.".format(target_type)) 

def agc_mixed_002_02(
            self, environment: Environment, template: str,
    ) -> Tuple[str, Optional[str], Callable]:
        """Returns the template source from the environment.

        This considers the loaders on the :attr:`app` and blueprints.
        """
        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        for loader in self.app.template_loaders:
            if hasattr(loader, "get_source"):
                source, path, uid = loader.get_source(environment, template)
                if source is not None:
                    return source, path, uid

        raise TemplateNotFound(template) 

def hwc_mixed_002_03(path):
    """Finds objects in pairtree.

    Given a path that corresponds to a pairtree, walk it and look for
    non-shorty (it's ya birthday) directories.
    """
    objects = []
    if not os.path.isdir(path):
        return []
    contents = os.listdir(path)
    for item in contents:
        fullPath = os.path.join(path, item)
        if not os.path.isdir(fullPath):
            # deal with a split end at this point
            # we might want to consider a normalize option
            return [path]
        else:
            if isShorty(item):
                objects = objects + findObjects(fullPath)
            else:
                objects.append(fullPath)
    return objects 

def hwc_mixed_002_04(self, file_path, upload_path = '', overwrite = False):
        """getDiskSpace

        Args:
            file_path: Full path for a file you want to checkUpload
            upload_path: Ndrive path where you want to upload file
                ex) /Picture/

        Returns:
            True: Possible to upload a file with a given file_size
            False: Impossible to upload a file with a given file_size

        """

        self.checkAccount()

        url = nurls['checkUpload']

        file_size = os.stat(file_path).st_size
        file_name = os.path.basename(file_path)

        now = datetime.datetime.now().isoformat()

        data = {'userid': self.user_id,
                'useridx': self.useridx,
                'getlastmodified': now,
                'dstresource': upload_path + file_name,
                'overwrite': overwrite,
                'uploadsize': file_size,
               }
        r = self.session.post(nurls['getDiskSpace'], data = data)

        return resultManager(r.text) 

def agc_mixed_002_05(self, ds):
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

def agc_mixed_002_06(ins):
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
