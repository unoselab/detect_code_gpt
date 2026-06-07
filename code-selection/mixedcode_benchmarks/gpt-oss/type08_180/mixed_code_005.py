def hwc_mixed_005_01(cls, fieldname, value):
        """
        A :class:`~urllib3.fields.RequestField` factory from old-style tuple parameters.

        Supports constructing :class:`~urllib3.fields.RequestField` from
        parameter of key/value strings AND key/filetuple. A filetuple is a
        (filename, data, MIME type) tuple where the MIME type is optional.
        For example::

            'foo': 'bar',
            'fakefile': ('foofile.txt', 'contents of foofile'),
            'realfile': ('barfile.txt', open('realfile').read()),
            'typedfile': ('bazfile.bin', open('bazfile').read(), 'image/jpeg'),
            'nonamefile': 'contents of nonamefile field',

        Field names and filenames must be unicode.
        """
        if isinstance(value, tuple):
            if len(value) == 3:
                filename, data, content_type = value
            else:
                filename, data = value
                content_type = guess_content_type(filename)
        else:
            filename = None
            content_type = None
            data = value

        request_param = cls(fieldname, data, filename=filename)
        request_param.make_multipart(content_type=content_type)

        return request_param 

def agc_mixed_005_02(context):
    """Setup before all tests.

    Initialize the logger framework.

    :param context: test context.
    """
    import logging

    logger = getattr(context, "logger", None)
    if logger is None:
        logger = logging.getLogger("tests")
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        context.logger = logger
    else:
        logger.setLevel(logging.DEBUG) 

def hwc_mixed_005_03(self):
        """
        Wait until the instance represented by this box is accessible via SSH.

        :return: the number of unsuccessful attempts to connect to the port before a the first
        success
        """
        logger.debug('Waiting for ssh port to open...')
        for i in count():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(a_short_time)
                s.connect((self.effectiveIP, 22))
                logger.debug('...ssh port open')
                return i
            except socket.error:
                pass
            finally:
                s.close() 

def agc_mixed_005_04(self, user_id, group_id):
        """
        移动用户分组

        详情请参考
        http://mp.weixin.qq.com/wiki/0/56d992c605a97245eb7e617854b169fc.html

        :param user_id: 用户 ID, 可以是单个或者列表，为列表时为批量移动用户分组
        :param group_id: 分组 ID
        :return: 返回的 JSON 数据包

        使用示例::

            from wechatpy import WeChatClient

            client = WeChatClient('appid', 'secret')
            res = client.group.move_user('openid', 1234)

        """
        if isinstance(user_id, (list, tuple, set)):
            url = 'https://api.weixin.qq.com/cgi-bin/groups/members/batchupdate'
            data = {
                'openid_list': list(user_id),
                'to_groupid': group_id
            }
        else:
            url = 'https://api.weixin.qq.com/cgi-bin/groups/members/update'
            data = {
                'openid': user_id,
                'to_groupid': group_id
            }
        return self._post(url, data) 

def hwc_mixed_005_05(self):
        """Modified ``run`` that captures return value and exceptions from ``target``"""
        try:
            if self._target:
                return_value = self._target(*self._args, **self._kwargs)
                if return_value is not None:
                    self._exception = OrphanedReturn(self, return_value)
        except BaseException as err:
            self._exception = err
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs 

def agc_mixed_005_06(num):
    # type: (int) -> float
    """
    Computes logfactorial regularly for tractable numbers, uses Ramanujans approximation otherwise.
    """

    import math
    if num <= 1:
        return 0.0
    # Use direct summation for small numbers where exactness is cheap
    if num < 20:
        s = 0.0
        for i in range(2, num + 1):
            s += math.log(i)
        return s
    # Ramanujan's approximation:
    # n! ≈ sqrt(pi) * (n/e)^n * (8n^3 + 4n^2 + n + 1/30)^(1/6)
    n = float(num)
    term1 = n * math.log(n) - n
    term2 = 0.5 * math.log(math.pi)
    term3 = (1.0 / 6.0) * math.log(8.0 * n ** 3 + 4.0 * n ** 2 + n + 1.0 / 30.0)
    return term1 + term2 + term3
