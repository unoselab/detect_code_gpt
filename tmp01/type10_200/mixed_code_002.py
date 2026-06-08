def hwc_mixed_002_01(self):
        """Return a list of attribute names for the mapping.

        :rtype: list

        """
        return sorted([k for k in dir(self) if
                       k[0:1] != '_' and k != 'keys' and not k.isupper() and
                       not inspect.ismethod(getattr(self, k)) and
                       not (hasattr(self.__class__, k) and
                            isinstance(getattr(self.__class__, k),
                                       property)) and
                       not isinstance(getattr(self, k), property)]) 

def hwc_mixed_002_02(self, filepath, fprogress):
        """Store file at filepath in the database and return the base index entry
        Needs the git_working_dir decorator active ! This must be assured in the calling code"""
        st = os.lstat(filepath)     # handles non-symlinks as well
        if S_ISLNK(st.st_mode):
            # in PY3, readlink is string, but we need bytes. In PY2, it's just OS encoded bytes, we assume UTF-8
            open_stream = lambda: BytesIO(force_bytes(os.readlink(filepath), encoding=defenc))
        else:
            open_stream = lambda: open(filepath, 'rb')
        with open_stream() as stream:
            fprogress(filepath, False, filepath)
            istream = self.repo.odb.store(IStream(Blob.type, st.st_size, stream))
            fprogress(filepath, True, filepath)
        return BaseIndexEntry((stat_mode_to_index_mode(st.st_mode),
                               istream.binsha, 0, to_native_path_linux(filepath))) 

def agc_mixed_002_03(self, value):
        """
        Returns a UTF-8 string representation of the parameter value,
        recursing into lists.
        """
        # Extract IDs from objects
        if isinstance(value, list):
            return '[' + ', '.join(self._process_param_value(v) for v in value) + ']'
        elif isinstance(value, dict):
            return '{' + ', '.join('%s: %s' % (k, self._process_param_value(v)) for k, v in value.items()) + '}'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, float):
            return str(value)
        elif isinstance(value, str):
            return value
        else:
            raise TypeError('Parameter value must be str, int, float, bool, list or dict') 

def hwc_mixed_002_04(src_bucket_name, src_bucket_secret_key, src_bucket_access_key,
                   dst_bucket_name, dst_bucket_secret_key, dst_bucket_access_key):
    """ Copy S3 bucket directory with CMS data between environments. Operations are done on server. """
    with cd(env.remote_path):
        tmp_dir = "s3_tmp"
        sudo('rm -rf %s' % tmp_dir, warn_only=True, user=env.remote_user)
        sudo('mkdir %s' % tmp_dir, user=env.remote_user)
        sudo('s3cmd --recursive get s3://%s/upload/ %s --secret_key=%s --access_key=%s' % (
            src_bucket_name, tmp_dir, src_bucket_secret_key, src_bucket_access_key),
            user=env.remote_user)
        sudo('s3cmd --recursive put %s/ s3://%s/upload/ --secret_key=%s --access_key=%s' % (
            tmp_dir, dst_bucket_name, dst_bucket_secret_key, dst_bucket_access_key),
            user=env.remote_user)

        sudo('s3cmd setacl s3://%s/upload --acl-public --recursive --secret_key=%s --access_key=%s' % (
             dst_bucket_name, dst_bucket_secret_key, dst_bucket_access_key),
             user=env.remote_user)
        # cleanup
        sudo('rm -rf %s' % tmp_dir, warn_only=True, user=env.remote_user) 

async def agc_mixed_002_05(
    host,
    port,
    *,
    loop=None,
    secure=True,
    ssl_context=None,
    **kwargs,
):
    """Open an HTTP/2 connection to the specified host/port.
    """
    if loop is None:
        loop = asyncio.get_event_loop()
    if ssl_context is None:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    if secure:
        ssl_context.set_alpn_protocols(["h2"])
        ssl_context.set_npn_protocols(["h2"])
    if ssl_context.check_hostname:
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    else:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    if ssl_context.ciphers is None:
        ssl_context.ciphers = "ECDHE+AESGCM"
    if ssl_context.cert_reqs == ssl.CERT_NONE:
        ssl_context.load_verify_locations(cafile=None)
    else:
        ssl_context.load_default_certs()
    if ssl_context.certfile is None:
        ssl_context.load_cert_chain(certfile=None)
    return await loop.create_connection(
        lambda: HTTP2Connection(ssl_context=ssl_context, **kwargs),
        host,
        port,
        ssl=ssl_context,
    ) 

def agc_mixed_002_06(self, domain, record_type, name=None, data=None):
        """
        Returns a list of all records configured for the specified domain that
        match the supplied search criteria.
        """
        if not name:
            name = ''
        if not data:
            data = ''
        return self.connection.request('domains/%s/records' % (domain),
                                       params={'type': record_type,
                                               'name': name,
                                               'data': data}).object
