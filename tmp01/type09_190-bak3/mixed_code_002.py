def hwc_mixed_002_01(self, file_path, upload_path = '', overwrite = False):
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

def agc_mixed_002_02(self):
        """
        Return the unicode XML snippet for the ``<c:val>`` element describing
        this series, containing the series values and their spreadsheet range
        reference.
        """
        values = self._values
        if values is None:
            values = self._values = self._series_values()
        value_xml = []
        for value in values:
            value_xml.append(
                '<c:ptCount val="{count}"/><c:numCache>{values}</c:numCache>'
               .format(
                    count=len(value),
                    values="".join(value)
                )
            )
        return "".join(value_xml) 

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

def agc_mixed_002_04(start, end, periods, offset):
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

def hwc_mixed_002_05(target_type, **kwargs):
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

def agc_mixed_002_06(self, device):
        """ Updates the device information based on files from its 'mount_point'
            @param device Dictionary containing device information
        """
        device_name = device['name']
        device_mount_point = device['mount_point']
        device_files = os.listdir(device_mount_point)
        for file_name in device_files:
            file_path = os.path.join(device_mount_point, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_modification_time = os.path.getmtime(file_path)
                device[file_name] = {
                   'size': file_size,
                   'modification_time': file_modification_time
                }
