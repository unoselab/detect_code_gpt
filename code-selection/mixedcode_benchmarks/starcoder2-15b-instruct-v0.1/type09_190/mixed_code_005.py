def hwc_mixed_005_01(self):
        """ Return handler capture statistics

        Return a dictionary of capture handler statistics of the form:

        .. code-block:: none

            [{
                'name': The handler's name,

                'reads': The number of packet reads this handler has received

                'data_read_length': The total length of the data received

                'approx_data_rate': The approximate data rate for this handler
            }, ...]

        """
        stats = []
        for h in self.capture_handlers:
            now = calendar.timegm(time.gmtime())
            rot_time = calendar.timegm(h['log_rot_time'])
            time_delta = now - rot_time
            approx_data_rate = '{} bytes/second'.format(h['data_read'] / float(time_delta))

            stats.append({
                'name': h['name'],
                'reads': h['reads'],
                'data_read_length': '{} bytes'.format(h['data_read']),
                'approx_data_rate': approx_data_rate
            })

        return stats 

def agc_mixed_005_02(start, end, periods, offset):
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

def agc_mixed_005_03(self, ostream, treeish=None, prefix=None, **kwargs):
        """Archive the tree at the given revision.

        :param ostream: file compatible stream object to which the archive will be written as bytes
        :param treeish: is the treeish name/id, defaults to active branch
        :param prefix: is the optional prefix to prepend to each filename in the archive
        :param kwargs: Additional arguments passed to git-archive

            * Use the 'format' argument to define the kind of format. Use
              specialized ostreams to write any format supported by python.
            * You may specify the special **path** keyword, which may either be a repository-relative
              path to a directory or file to place into the archive, or a list or tuple of multiple paths.

        :raise GitCommandError: in case something went wrong
        :return: self"""
        if treeish is None:
            treeish = self.active_branch
        cmd = ['git', 'archive']
        if prefix is not None:
            cmd.extend(['--prefix', prefix])
        cmd.extend([treeish, '--output', ostream.name])
        if 'format' in kwargs:
            cmd.extend(['--format', kwargs['format']])
        if 'path' in kwargs:
            if isinstance(kwargs['path'], (list, tuple)):
                cmd.extend(kwargs['path'])
            else:
                cmd.append(kwargs['path'])
        self.git.execute(cmd)
        return self 

def hwc_mixed_005_04(client):
        """Returns a list of all the roles for an account. Returns a list containing all the roles for the account.

        Args:
            client (:obj:`boto3.session.Session`): A boto3 Session object

        Returns:
            :obj:`list` of `dict`
        """
        done = False
        marker = None
        roles = []

        while not done:
            if marker:
                response = client.list_roles(Marker=marker)
            else:
                response = client.list_roles()

            roles += response['Roles']

            if response['IsTruncated']:
                marker = response['Marker']
            else:
                done = True

        return roles 

def hwc_mixed_005_05(cls, d, encoding='base64'):
        """
        Construct a ``Report`` object from dictionary.

        :type d: dictionary
        :param d: dictionary representing the report
        :param encoding: encoding of strings in the dictionary (default: 'base64')
        :return: Report object
        """
        report = Report(Report._decode(d['name'], encoding))
        report.set_status(Report._decode(d['status'], encoding))
        sub_reports = Report._decode(d['sub_reports'], encoding)
        del d['sub_reports']
        for k, v in d.items():
            if k in sub_reports:
                report.add(k, Report.from_dict(v))
            else:
                if k.lower() == 'status':
                    report.set_status(Report._decode(v, encoding))
                else:
                    report.add(k, Report._decode(v, encoding))

        return report 

def agc_mixed_005_06(self):
        """Create a property dict that is used to recreate an edge dictionary for a :class:`BELGraph`.

        :return: Property dictionary of an edge that is participant (sub/obj) related.
        :rtype: dict
        """
        return {
            "subject": self.subject,
            "object": self.object,
            "relation": self.relation,
            "name": self.name,
            "namespace": self.namespace,
            "identifier": self.identifier,
            "resource": self.resource,
            "variant": self.variant,
            "location": self.location,
            "evidence": self.evidence,
            "annotations": self.annotations,
            "citation": self.citation,
            "support": self.support,
        }
