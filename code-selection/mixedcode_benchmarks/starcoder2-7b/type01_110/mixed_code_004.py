def hwc_mixed_004_01(self, devices, op_type=1):
        """
        设备授权
        详情请参考
        https://iot.weixin.qq.com/wiki/new/index.html?page=3-4-5

        :param devices: 设备信息的列表
        :param op_type: 请求操作的类型，限定取值为：0：设备授权 1：设备更新
        :return: 返回的 JSON 数据包
        """
        return self._post(
            'authorize_device',
            data={
                'device_num': len(devices),
                'device_list': devices,
                'op_type': op_type
            }
        ) 

def agc_mixed_004_02(self, table, columns, values, where):
        """
        Update the values of a particular row where a value is met.

        :param table: table name
        :param columns: column(s) to update
        :param values: updated values
        :param where: tuple, (where_column, where_value)
        """
        # Unpack WHERE clause dictionary into tuple
        if isinstance(columns, str):
            columns = [columns]
        if isinstance(values, str):
            values = [values]
        if isinstance(where, str):
            where = [where]

        query = "UPDATE {} SET {} WHERE {} =?".format(table, self._make_query(columns, values), where[0])
        self._cursor.execute(query, where[1])
        self._connection.commit() 

def agc_mixed_004_03(endpoint, filename=None, **values):
    """
    This function acts as "replacement" for the default url_for() and intercepts if it is a request for bower assets

    If the file is not available in bower, the result is passed to flasks url_for().
    This is useful - but not recommended - for "overlaying" the static directory (see README.rst).
    """
    if endpoint == 'bower_static':
        if filename is None:
            return url_for('bower_static', filename='index.html')
        else:
            try:
                return url_for('bower_static', filename=filename)
            except:
                pass
    return url_for(endpoint, **values) 

def hwc_mixed_004_04(self):
    """Use the --libc-dir option if provided, otherwise invoke a host compiler to find libc dev."""
    libc_dir_option = self.get_options().libc_dir
    if libc_dir_option:
      maybe_libc_crti = os.path.join(libc_dir_option, self._LIBC_INIT_OBJECT_FILE)
      if os.path.isfile(maybe_libc_crti):
        return HostLibcDev(crti_object=maybe_libc_crti,
                           fingerprint=hash_file(maybe_libc_crti))
      raise self.HostLibcDevResolutionError(
        "Could not locate {} in directory {} provided by the --libc-dir option."
        .format(self._LIBC_INIT_OBJECT_FILE, libc_dir_option))

    return self._get_host_libc_from_host_compiler() 

def agc_mixed_004_05(self, action, properties, event_severity=EVENT_SEVERITY):
        """
        send css_event and if fails send custom_event instead
        Args:
            action (ACTIONS): the action causing the event
            properties (dict): the action additional properties
            event_severity (string): the event severity
        Raises:
            XCLIError: if the xcli.cmd.custom_event failed
            KeyError: if action wasn't predefined
            TypeError: if properties is not None or dict
        """
        # verify properties
        if not isinstance(properties, dict):
            raise TypeError("properties must be a dict")
        if action not in ACTIONS:
            raise KeyError("action must be one of the predefined actions")
        try:
            self.xcli.cmd.css_event(action, properties, event_severity)
        except XCLIError:
            self.xcli.cmd.custom_event(action, properties, event_severity) 

def hwc_mixed_004_06(self, point):
        """
        Convert a point to an index in the matrix array.

        Parameters
        ----------
        point: (3,) float, point in space

        Returns
        ---------
        index: (3,) int tuple, index in self.matrix
        """
        indices = points_to_indices(points=[point],
                                    pitch=self.pitch,
                                    origin=self.origin)
        index = tuple(indices[0])
        return index
